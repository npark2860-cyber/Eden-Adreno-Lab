#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <utility>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

#include "common/settings.h"
#include "common/settings_enums.h"
#include "core/arm/arm_interface.h"
#include "core/arm/nce/patcher.h"
#include "core/arm/nce/x18_fallback.h"
#include "core/arm/nce/x18_site_patcher.h"
#include "core/core.h"
#include "core/device_memory.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/code_set.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/kernel.h"
#include "core/hle/kernel/svc_types.h"

#ifdef interface
#undef interface
#endif

namespace {

constexpr std::size_t PageSize = 0x1000;
constexpr std::size_t InitialImageSize = PageSize * 2;
constexpr std::size_t GuestCodeOffset = 0x24;
constexpr std::size_t GuestX0Offset = 0x28;
constexpr std::size_t GuestSvcOffset = 0x2c;
constexpr std::size_t GuestAfterSvcOffset = 0x30;

constexpr u32 GuestAddX18One = 0x91000652; // add x18, x18, #1
constexpr u32 GuestAddX0One = 0x91000400;  // add x0, x0, #1
constexpr u32 GuestSvc55 = 0xD4000AA1;     // svc #0x55
constexpr u32 GuestBrk0 = 0xD4200000;      // must never execute in E5

constexpr u64 GuestX18Initial = 0x123456789ABC0000ull;
constexpr u64 GuestX18Expected = GuestX18Initial + 1;
constexpr u64 GuestX0Initial = 0x41;
constexpr u64 GuestX0Expected = GuestX0Initial + 1;

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cerr << marker << "=PASS\n" << std::flush;
}

#if defined(_WIN32)
std::uint64_t ReadPhysicalX18() {
    std::uint64_t value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

LONG CALLBACK E5VectoredExceptionHandler(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto* const record = exception->ExceptionRecord;
    std::fprintf(stderr, "IMP008B_E5_EXCEPTION_CODE=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionCode));
    std::fprintf(stderr, "IMP008B_E5_EXCEPTION_FLAGS=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionFlags));
    std::fprintf(stderr, "IMP008B_E5_EXCEPTION_ADDRESS=%p\n", record->ExceptionAddress);
#if defined(_M_ARM64) || defined(__aarch64__)
    if (exception->ContextRecord != nullptr) {
        std::fprintf(stderr, "IMP008B_E5_EXCEPTION_PC=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Pc));
        std::fprintf(stderr, "IMP008B_E5_EXCEPTION_SP=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Sp));
        std::fprintf(stderr, "IMP008B_E5_EXCEPTION_PHYSICAL_X18=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->X18));
    }
#endif
    std::fflush(stderr);
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

std::size_t PageAlign(std::size_t value) {
    return (value + PageSize - 1) & ~(PageSize - 1);
}

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008B_E5_PLATFORM_CONTRACT");
#else
    Trace("IMP008B_E5_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008B_E5_NCE_SETTING");
    }
    Trace("IMP008B_E5_SETTINGS_READY");

    if (Core::NCE::X18Fallback::ClassifyInstruction(GuestAddX18One) !=
        Core::NCE::X18InstructionClass::SupportedOrdinary) {
        return Fail("IMP008B_E5_X18_CLASSIFICATION");
    }
    Trace("IMP008B_E5_X18_CLASSIFIED");

    Kernel::CodeSet code_set;
    code_set.memory.resize(InitialImageSize);
    auto& code = code_set.CodeSegment();
    code.offset = 0;
    code.addr = Kernel::KProcessAddress{0};
    code.size = static_cast<u32>(PageSize);
    auto& ro = code_set.RODataSegment();
    ro.offset = PageSize;
    ro.addr = Kernel::KProcessAddress{PageSize};
    ro.size = 0;
    auto& data = code_set.DataSegment();
    data.offset = PageSize;
    data.addr = Kernel::KProcessAddress{PageSize};
    data.size = static_cast<u32>(PageSize);

    auto* const words = reinterpret_cast<u32*>(code_set.memory.data());
    words[GuestCodeOffset / sizeof(u32)] = GuestAddX18One;
    words[GuestX0Offset / sizeof(u32)] = GuestAddX0One;
    words[GuestSvcOffset / sizeof(u32)] = GuestSvc55;
    words[GuestAfterSvcOffset / sizeof(u32)] = GuestBrk0;
    Trace("IMP008B_E5_CODESET_READY");

    const auto x18_sites = Core::NCE::X18SitePatcher::Collect(code_set.memory, code);
    if (x18_sites.size() != 1 ||
        x18_sites.front().text_word_index != GuestCodeOffset / sizeof(u32) ||
        x18_sites.front().instruction != GuestAddX18One) {
        return Fail("IMP008B_E5_X18_SITE_COLLECT");
    }
    Trace("IMP008B_E5_X18_SITE_COLLECTED");

    Core::NCE::Patcher patcher;
    Trace("IMP008B_E5_PATCH_BEGIN");
    if (!patcher.PatchText(code_set.memory, code)) {
        return Fail("IMP008B_E5_PATCH_TEXT");
    }
    if (patcher.GetPatchMode() != Core::NCE::PatchMode::PostData) {
        return Fail("IMP008B_E5_PATCH_MODE");
    }
    const std::size_t patch_size = patcher.GetSectionSize();
    if (patch_size == 0) {
        return Fail("IMP008B_E5_PATCH_SIZE");
    }
    Trace("IMP008B_E5_PATCH_READY");

    Core::System system;
    Trace("IMP008B_E5_SYSTEM_INIT_BEGIN");
    system.Initialize();
    Trace("IMP008B_E5_SYSTEM_INIT_DONE");
    auto& kernel = system.Kernel();
    Trace("IMP008B_E5_KERNEL_INIT_BEGIN");
    kernel.Initialize();
    Trace("IMP008B_E5_KERNEL_INIT_DONE");

    auto& direct_buffer = system.DeviceMemory().buffer;
    Trace("IMP008B_E5_DIRECT_MAP_BEGIN");
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    std::fprintf(stderr, "IMP008B_E5_FASTMEM_BASE=0x%llX\n",
                 static_cast<unsigned long long>(fastmem_base));
    std::fflush(stderr);
    Trace("IMP008B_E5_DIRECT_MAP_DONE");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008B_E5_PROCESS_CREATE");
    }
    Trace("IMP008B_E5_PROCESS_CREATED");

    PVOID diagnostic_veh = AddVectoredExceptionHandler(1, &E5VectoredExceptionHandler);
    if (diagnostic_veh == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_VEH_INSTALL");
    }
    Trace("IMP008B_E5_VEH_INSTALLED");

    const std::size_t mapped_code_size = PageAlign(InitialImageSize + patch_size);
    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    Trace("IMP008B_E5_PROCESS_LOAD_BEGIN");
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, mapped_code_size, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_PROCESS_LOAD");
    }
    Trace("IMP008B_E5_PROCESS_LOAD_DONE");
    std::cout << "IMP008B_E5_REAL_PROCESS=PASS\n" << std::flush;

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    const std::size_t image_size_before_relocate = code_set.memory.size();

    Trace("IMP008B_E5_RELOCATE_BEGIN");
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                 &process->GetPostHandlers())) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_RELOCATE");
    }
    Trace("IMP008B_E5_RELOCATE_DONE");

    Core::NCE::X18SitePatcher::Apply(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                     x18_sites, process->GetPostHandlers());
    const u64 x18_runtime_pc = load_base_u64 + GuestCodeOffset;
    const auto metadata_it =
        process->GetPostHandlers().find(Core::NCE::X18SitePatcher::MetadataKey(x18_runtime_pc));
    if (metadata_it == process->GetPostHandlers().end() ||
        metadata_it->second != Core::NCE::X18SitePatcher::MetadataValue(GuestAddX18One)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_X18_METADATA");
    }
    Trace("IMP008B_E5_X18_METADATA_READY");

    auto& patch_segment = code_set.PatchSegment();
    patch_segment.offset = image_size_before_relocate;
    patch_segment.addr = Kernel::KProcessAddress{image_size_before_relocate};
    patch_segment.size = static_cast<u32>(patch_size);

    Trace("IMP008B_E5_LOAD_MODULE_BEGIN");
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008B_E5_LOAD_MODULE_DONE");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_THREAD_CREATE");
    }
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_THREAD_OWNER");
    }
    std::cout << "IMP008B_E5_REAL_KTHREAD=PASS\n" << std::flush;

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_INTERFACE_NULL");
    }

    const u64 guest_pc = load_base_u64 + GuestCodeOffset;
    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;
    Kernel::Svc::ThreadContext context{};
    context.r[0] = GuestX0Initial;
    context.r[18] = GuestX18Initial;
    context.sp = guest_sp;
    context.pc = guest_pc;
    context.pstate = 0;
    interface->SetContext(context);
    interface->SetTpidrroEl0(0);
    interface->Initialize();
    interface->ClearInstructionCache();
    Trace("IMP008B_E5_CONTEXT_READY");

    const u64 teb = reinterpret_cast<u64>(NtCurrentTeb());
    const u64 physical_x18_before = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008B_E5_TEB=0x%llX\n", static_cast<unsigned long long>(teb));
    std::fprintf(stderr, "IMP008B_E5_PHYSICAL_X18_BEFORE=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_before));
    std::fprintf(stderr, "IMP008B_E5_GUEST_X18_INITIAL=0x%llX\n",
                 static_cast<unsigned long long>(GuestX18Initial));
    std::fflush(stderr);
    if (physical_x18_before != teb) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_PHYSICAL_X18_TEB_BEFORE");
    }
    std::cout << "IMP008B_E5_PHYSICAL_X18_TEB_BEFORE=PASS\n" << std::flush;

    std::cout << "IMP008B_E5_PRE_RUNTHREAD=PASS\n" << std::flush;
    interface->LockThread(thread);
    const Core::HaltReason halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    std::cout << "IMP008B_E5_RUNTHREAD_RETURNED=PASS\n" << std::flush;

    const u64 physical_x18_after = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008B_E5_PHYSICAL_X18_AFTER=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_after));
    std::fflush(stderr);

    if (!True(halt_reason & Core::HaltReason::SupervisorCall)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_HALT_REASON");
    }
    if (interface->GetSvcNumber() != 0x55) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_SVC_NUMBER");
    }

    Kernel::Svc::ThreadContext returned{};
    interface->GetContext(returned);
    if (returned.r[18] != GuestX18Expected) {
        std::fprintf(stderr, "IMP008B_E5_GUEST_X18_RETURNED=0x%llX EXPECTED=0x%llX\n",
                     static_cast<unsigned long long>(returned.r[18]),
                     static_cast<unsigned long long>(GuestX18Expected));
        std::fflush(stderr);
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_GUEST_X18_RESULT");
    }
    std::cout << "IMP008B_E5_GUEST_X18_EXECUTED=PASS\n" << std::flush;

    if (returned.r[0] != GuestX0Expected || returned.pc != load_base_u64 + GuestAfterSvcOffset ||
        returned.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_ARCH_CONTEXT");
    }
    std::cout << "IMP008B_E5_SVC_RETURN=PASS\n";
    std::cout << "IMP008B_E5_ARCH_CONTEXT_COHERENT=PASS\n" << std::flush;

    if (physical_x18_after != teb) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E5_PHYSICAL_X18_TEB_AFTER");
    }
    std::cout << "IMP008B_E5_PHYSICAL_X18_TEB_AFTER=PASS\n" << std::flush;

    RemoveVectoredExceptionHandler(diagnostic_veh);
    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    std::cout << "IMP008B_E5_GATE=PASS\n" << std::flush;
    return 0;
#endif
}
