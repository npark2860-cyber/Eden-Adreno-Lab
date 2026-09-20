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
constexpr std::size_t GuestFirstSvcOffset = 0x28;
constexpr std::size_t GuestAfterFirstSvcOffset = 0x2c;
constexpr std::size_t GuestReadNzcvOffset = 0x30;
constexpr std::size_t GuestSecondSvcOffset = 0x34;
constexpr std::size_t GuestAfterSecondSvcOffset = 0x38;
constexpr u32 GuestAddsX0One = 0xB1000400; // adds x0, x0, #1
constexpr u32 GuestSvc33 = 0xD4000661;     // svc #0x33
constexpr u32 GuestAddX18One = 0x91000652; // add x18, x18, #1
constexpr u32 GuestMrsX0Nzcv = 0xD53B4200; // mrs x0, NZCV
constexpr u32 GuestSvc44 = 0xD4000881;     // svc #0x44
constexpr u32 GuestBrk0 = 0xD4200000;      // must never execute
constexpr u32 NzcvMask = 0xF0000000U;
constexpr u32 FirstExpectedNzcv = 0x60000000U;
constexpr u32 HostInjectedNzcv = 0xA0000000U;
constexpr u64 GuestX18Initial = 0x123456789ABC0000ULL;
constexpr u64 GuestX18Expected = GuestX18Initial + 1;

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cerr << marker << "=PASS\n" << std::flush;
}

#if defined(_WIN32)
LONG CALLBACK D1NzcvVectoredExceptionHandler(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto* const record = exception->ExceptionRecord;
    std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_CODE=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionCode));
    std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_FLAGS=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionFlags));
    std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_ADDRESS=%p\n", record->ExceptionAddress);
    std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_PARAMETER_COUNT=%lu\n",
                 static_cast<unsigned long>(record->NumberParameters));
    for (ULONG i = 0; i < record->NumberParameters && i < EXCEPTION_MAXIMUM_PARAMETERS; ++i) {
        std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_PARAMETER_%lu=0x%llX\n",
                     static_cast<unsigned long>(i),
                     static_cast<unsigned long long>(record->ExceptionInformation[i]));
    }
#if defined(_M_ARM64) || defined(__aarch64__)
    if (exception->ContextRecord != nullptr) {
        std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_PC=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Pc));
        std::fprintf(stderr, "IMP008_D1_NZCV_EXCEPTION_SP=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Sp));
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
    return Fail("IMP008_D1_NZCV_PLATFORM_CONTRACT");
#else
    Trace("IMP008_D1_NZCV_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008_D1_NZCV_NCE_SETTING");
    }
    Trace("IMP008_D1_NZCV_SETTINGS_READY");

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
    words[GuestCodeOffset / sizeof(u32)] = GuestAddsX0One;
    words[GuestFirstSvcOffset / sizeof(u32)] = GuestSvc33;
    words[GuestAfterFirstSvcOffset / sizeof(u32)] = GuestAddX18One;
    words[GuestReadNzcvOffset / sizeof(u32)] = GuestMrsX0Nzcv;
    words[GuestSecondSvcOffset / sizeof(u32)] = GuestSvc44;
    words[GuestAfterSecondSvcOffset / sizeof(u32)] = GuestBrk0;
    Trace("IMP008_D1_NZCV_CODESET_READY");

    if (Core::NCE::X18Fallback::ClassifyInstruction(GuestAddX18One) !=
        Core::NCE::X18InstructionClass::SupportedOrdinary) {
        return Fail("IMP008_D1_NZCV_X18_CLASSIFICATION");
    }
    const auto x18_sites = Core::NCE::X18SitePatcher::Collect(code_set.memory, code);
    if (x18_sites.size() != 1 ||
        x18_sites.front().text_word_index != GuestAfterFirstSvcOffset / sizeof(u32) ||
        x18_sites.front().instruction != GuestAddX18One) {
        return Fail("IMP008_D1_NZCV_X18_SITE_COLLECT");
    }
    Trace("IMP008_D1_NZCV_X18_SITE_READY");

    Core::NCE::Patcher patcher;
    Trace("IMP008_D1_NZCV_PATCH_BEGIN");
    if (!patcher.PatchText(code_set.memory, code)) {
        return Fail("IMP008_D1_NZCV_PATCH_TEXT");
    }
    if (patcher.GetPatchMode() != Core::NCE::PatchMode::PostData) {
        return Fail("IMP008_D1_NZCV_PATCH_MODE");
    }
    const std::size_t patch_size = patcher.GetSectionSize();
    if (patch_size == 0) {
        return Fail("IMP008_D1_NZCV_PATCH_SIZE");
    }
    Trace("IMP008_D1_NZCV_PATCH_READY");

    Core::System system;
    Trace("IMP008_D1_NZCV_SYSTEM_INIT_BEGIN");
    system.Initialize();
    Trace("IMP008_D1_NZCV_SYSTEM_INIT_DONE");
    auto& kernel = system.Kernel();
    Trace("IMP008_D1_NZCV_KERNEL_INIT_BEGIN");
    kernel.Initialize();
    Trace("IMP008_D1_NZCV_KERNEL_INIT_DONE");

    auto& direct_buffer = system.DeviceMemory().buffer;
    Trace("IMP008_D1_NZCV_DIRECT_MAP_BEGIN");
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    std::fprintf(stderr, "IMP008_D1_NZCV_FASTMEM_BASE=0x%llX\n",
                 static_cast<unsigned long long>(fastmem_base));
    std::fflush(stderr);
    Trace("IMP008_D1_NZCV_DIRECT_MAP_DONE");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_PROCESS_CREATE");
    }
    Trace("IMP008_D1_NZCV_PROCESS_CREATED");

    PVOID diagnostic_veh = AddVectoredExceptionHandler(1, &D1NzcvVectoredExceptionHandler);
    if (diagnostic_veh == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_VEH_INSTALL");
    }
    const HMODULE module_base = GetModuleHandleW(nullptr);
    std::fprintf(stderr, "IMP008_D1_NZCV_MODULE_BASE=%p\n", module_base);
    std::fflush(stderr);
    Trace("IMP008_D1_NZCV_VEH_INSTALLED");

    const std::size_t mapped_code_size = PageAlign(InitialImageSize + patch_size);
    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    Trace("IMP008_D1_NZCV_PROCESS_LOAD_BEGIN");
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, mapped_code_size, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_PROCESS_LOAD");
    }
    Trace("IMP008_D1_NZCV_PROCESS_LOAD_DONE");
    std::cout << "IMP008_D1_NZCV_REAL_PROCESS=PASS\n" << std::flush;

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    const std::size_t image_size_before_relocate = code_set.memory.size();
    Trace("IMP008_D1_NZCV_RELOCATE_BEGIN");
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                 &process->GetPostHandlers())) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_RELOCATE");
    }
    Trace("IMP008_D1_NZCV_RELOCATE_DONE");

    Core::NCE::X18SitePatcher::Apply(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                     x18_sites, process->GetPostHandlers());
    const u64 x18_runtime_pc = load_base_u64 + GuestAfterFirstSvcOffset;
    const auto x18_metadata =
        process->GetPostHandlers().find(Core::NCE::X18SitePatcher::MetadataKey(x18_runtime_pc));
    if (x18_metadata == process->GetPostHandlers().end() ||
        x18_metadata->second != Core::NCE::X18SitePatcher::MetadataValue(GuestAddX18One)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_X18_METADATA");
    }
    Trace("IMP008_D1_NZCV_X18_METADATA_READY");

    auto& patch_segment = code_set.PatchSegment();
    patch_segment.offset = image_size_before_relocate;
    patch_segment.addr = Kernel::KProcessAddress{image_size_before_relocate};
    patch_segment.size = static_cast<u32>(patch_size);

    Trace("IMP008_D1_NZCV_LOAD_MODULE_BEGIN");
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008_D1_NZCV_LOAD_MODULE_DONE");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_THREAD_CREATE");
    }
    Trace("IMP008_D1_NZCV_THREAD_CREATED");
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_THREAD_OWNER");
    }
    Trace("IMP008_D1_NZCV_THREAD_INIT_DONE");
    std::cout << "IMP008_D1_NZCV_REAL_KTHREAD=PASS\n" << std::flush;

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_INTERFACE_NULL");
    }

    const u64 guest_pc = load_base_u64 + GuestCodeOffset;
    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;

    Kernel::Svc::ThreadContext context{};
    context.r[0] = UINT64_MAX;
    context.r[18] = GuestX18Initial;
    context.sp = guest_sp;
    context.pc = guest_pc;
    context.pstate = 0;
    Trace("IMP008_D1_NZCV_CONTEXT_SET_BEGIN");
    interface->SetContext(context);
    interface->SetTpidrroEl0(0);
    interface->Initialize();
    interface->ClearInstructionCache();
    Trace("IMP008_D1_NZCV_CONTEXT_SET_DONE");

    std::fprintf(stderr, "IMP008_D1_NZCV_LOAD_BASE=0x%llX\n",
                 static_cast<unsigned long long>(load_base_u64));
    std::fprintf(stderr, "IMP008_D1_NZCV_GUEST_PC=0x%llX\n",
                 static_cast<unsigned long long>(guest_pc));
    std::fprintf(stderr, "IMP008_D1_NZCV_GUEST_SP=0x%llX\n",
                 static_cast<unsigned long long>(guest_sp));
    std::fflush(stderr);

    // D1 regression part 1: ADDS changes NZCV from 0 to Z|C before the first SVC.
    std::cout << "IMP008_D1_NZCV_PRE_FIRST_RUNTHREAD=PASS\n" << std::flush;
    interface->LockThread(thread);
    const Core::HaltReason first_halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    std::cout << "IMP008_D1_NZCV_FIRST_RUNTHREAD_RETURNED=PASS\n" << std::flush;

    if (!True(first_halt_reason & Core::HaltReason::SupervisorCall) ||
        interface->GetSvcNumber() != 0x33) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_FIRST_SVC_CONTRACT");
    }

    Kernel::Svc::ThreadContext first_returned{};
    interface->GetContext(first_returned);
    if (first_returned.r[0] != 0 ||
        first_returned.pc != load_base_u64 + GuestAfterFirstSvcOffset ||
        first_returned.sp != guest_sp ||
        (first_returned.pstate & NzcvMask) != FirstExpectedNzcv) {
        std::fprintf(stderr,
                     "IMP008_D1_NZCV_FIRST_CONTEXT x0=0x%llX pc=0x%llX sp=0x%llX "
                     "pstate=0x%08X expected_nzcv=0x%08X\n",
                     static_cast<unsigned long long>(first_returned.r[0]),
                     static_cast<unsigned long long>(first_returned.pc),
                     static_cast<unsigned long long>(first_returned.sp),
                     first_returned.pstate, FirstExpectedNzcv);
        std::fflush(stderr);
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SVC_SAVE_COHERENCE");
    }
    std::cout << "IMP008_D1_NZCV_SVC_SAVE_COHERENCE=PASS\n" << std::flush;

    // D1 regression part 2: inject a different scheduler pstate. The next instruction uses x18
    // and therefore passes through the one-step fallback, which consumes GuestContext::nzcv.
    first_returned.pstate = (first_returned.pstate & ~NzcvMask) | HostInjectedNzcv;
    interface->SetContext(first_returned);

    Kernel::Svc::ThreadContext edited{};
    interface->GetContext(edited);
    if ((edited.pstate & NzcvMask) != HostInjectedNzcv ||
        edited.pc != load_base_u64 + GuestAfterFirstSvcOffset || edited.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SCHEDULER_INPUT");
    }
    std::cout << "IMP008_D1_NZCV_SCHEDULER_INPUT=PASS\n" << std::flush;

    std::cout << "IMP008_D1_NZCV_PRE_SECOND_RUNTHREAD=PASS\n" << std::flush;
    interface->LockThread(thread);
    const Core::HaltReason second_halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    std::cout << "IMP008_D1_NZCV_SECOND_RUNTHREAD_RETURNED=PASS\n" << std::flush;

    if (!True(second_halt_reason & Core::HaltReason::SupervisorCall) ||
        interface->GetSvcNumber() != 0x44) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SECOND_SVC_CONTRACT");
    }

    Kernel::Svc::ThreadContext second_returned{};
    interface->GetContext(second_returned);
    if (second_returned.r[0] != HostInjectedNzcv ||
        second_returned.r[18] != GuestX18Expected ||
        second_returned.pc != load_base_u64 + GuestAfterSecondSvcOffset ||
        second_returned.sp != guest_sp ||
        (second_returned.pstate & NzcvMask) != HostInjectedNzcv) {
        std::fprintf(stderr,
                     "IMP008_D1_NZCV_SECOND_CONTEXT x0=0x%llX x18=0x%llX pc=0x%llX sp=0x%llX "
                     "pstate=0x%08X expected_nzcv=0x%08X\n",
                     static_cast<unsigned long long>(second_returned.r[0]),
                     static_cast<unsigned long long>(second_returned.r[18]),
                     static_cast<unsigned long long>(second_returned.pc),
                     static_cast<unsigned long long>(second_returned.sp),
                     second_returned.pstate, HostInjectedNzcv);
        std::fflush(stderr);
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_REENTRY_COHERENCE");
    }

    std::cout << "IMP008_D1_NZCV_X18_FALLBACK_PRESERVED=PASS\n";
    std::cout << "IMP008_D1_NZCV_REENTRY_COHERENCE=PASS\n" << std::flush;

    RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SECOND_HALT_REASON");
    }
    if (interface->GetSvcNumber() != 0x44) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SECOND_SVC_NUMBER");
    }

    Kernel::Svc::ThreadContext second_returned{};
    interface->GetContext(second_returned);
    if (second_returned.r[0] != SecondReturnedX0) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_REENTRY_GUEST_EXECUTED");
    }
    if (second_returned.pc != load_base_u64 + GuestAfterSecondSvcOffset) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SECOND_RETURN_PC");
    }
    if (second_returned.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008_D1_NZCV_SECOND_RETURN_SP");
    }

    std::cout << "IMP008_D1_NZCV_REENTRY_GUEST_EXECUTED=PASS\n";
    std::cout << "IMP008_D1_NZCV_SECOND_SVC_RETURN=PASS\n";
    std::cout << "IMP008_D1_NZCV_CONTEXT_COHERENT=PASS\n" << std::flush;

    RemoveVectoredExceptionHandler(diagnostic_veh);
    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    std::cout << "IMP008_D1_NZCV_GATE=PASS\n" << std::flush;
    return 0;
#endif
}
