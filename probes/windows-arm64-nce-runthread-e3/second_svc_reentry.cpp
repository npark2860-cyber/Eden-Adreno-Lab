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
constexpr std::size_t GuestSecondSvcOffset = 0x30;
constexpr std::size_t GuestAfterSecondSvcOffset = 0x34;
constexpr u32 GuestAddX0One = 0x91000400; // add x0, x0, #1
constexpr u32 GuestSvc33 = 0xD4000661;    // svc #0x33
constexpr u32 GuestAddX0Two = 0x91000800; // add x0, x0, #2
constexpr u32 GuestSvc44 = 0xD4000881;    // svc #0x44
constexpr u32 GuestBrk0 = 0xD4200000;     // must never execute in E3
constexpr u64 HostEditedX0 = 0x80;
constexpr u64 SecondReturnedX0 = HostEditedX0 + 2;

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cerr << marker << "=PASS\n" << std::flush;
}

#if defined(_WIN32)
LONG CALLBACK E3VectoredExceptionHandler(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto* const record = exception->ExceptionRecord;
    std::fprintf(stderr, "IMP008B_E3_EXCEPTION_CODE=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionCode));
    std::fprintf(stderr, "IMP008B_E3_EXCEPTION_FLAGS=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionFlags));
    std::fprintf(stderr, "IMP008B_E3_EXCEPTION_ADDRESS=%p\n", record->ExceptionAddress);
    std::fprintf(stderr, "IMP008B_E3_EXCEPTION_PARAMETER_COUNT=%lu\n",
                 static_cast<unsigned long>(record->NumberParameters));
    for (ULONG i = 0; i < record->NumberParameters && i < EXCEPTION_MAXIMUM_PARAMETERS; ++i) {
        std::fprintf(stderr, "IMP008B_E3_EXCEPTION_PARAMETER_%lu=0x%llX\n",
                     static_cast<unsigned long>(i),
                     static_cast<unsigned long long>(record->ExceptionInformation[i]));
    }
#if defined(_M_ARM64) || defined(__aarch64__)
    if (exception->ContextRecord != nullptr) {
        std::fprintf(stderr, "IMP008B_E3_EXCEPTION_PC=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Pc));
        std::fprintf(stderr, "IMP008B_E3_EXCEPTION_SP=0x%llX\n",
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
    return Fail("IMP008B_E3_PLATFORM_CONTRACT");
#else
    Trace("IMP008B_E3_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008B_E3_NCE_SETTING");
    }
    Trace("IMP008B_E3_SETTINGS_READY");

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
    words[GuestCodeOffset / sizeof(u32)] = GuestAddX0One;
    words[GuestFirstSvcOffset / sizeof(u32)] = GuestSvc33;
    words[GuestAfterFirstSvcOffset / sizeof(u32)] = GuestAddX0Two;
    words[GuestSecondSvcOffset / sizeof(u32)] = GuestSvc44;
    words[GuestAfterSecondSvcOffset / sizeof(u32)] = GuestBrk0;
    Trace("IMP008B_E3_CODESET_READY");

    Core::NCE::Patcher patcher;
    Trace("IMP008B_E3_PATCH_BEGIN");
    if (!patcher.PatchText(code_set.memory, code)) {
        return Fail("IMP008B_E3_PATCH_TEXT");
    }
    if (patcher.GetPatchMode() != Core::NCE::PatchMode::PostData) {
        return Fail("IMP008B_E3_PATCH_MODE");
    }
    const std::size_t patch_size = patcher.GetSectionSize();
    if (patch_size == 0) {
        return Fail("IMP008B_E3_PATCH_SIZE");
    }
    Trace("IMP008B_E3_PATCH_READY");

    Core::System system;
    Trace("IMP008B_E3_SYSTEM_INIT_BEGIN");
    system.Initialize();
    Trace("IMP008B_E3_SYSTEM_INIT_DONE");
    auto& kernel = system.Kernel();
    Trace("IMP008B_E3_KERNEL_INIT_BEGIN");
    kernel.Initialize();
    Trace("IMP008B_E3_KERNEL_INIT_DONE");

    auto& direct_buffer = system.DeviceMemory().buffer;
    Trace("IMP008B_E3_DIRECT_MAP_BEGIN");
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    std::fprintf(stderr, "IMP008B_E3_FASTMEM_BASE=0x%llX\n",
                 static_cast<unsigned long long>(fastmem_base));
    std::fflush(stderr);
    Trace("IMP008B_E3_DIRECT_MAP_DONE");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008B_E3_PROCESS_CREATE");
    }
    Trace("IMP008B_E3_PROCESS_CREATED");

    PVOID diagnostic_veh = AddVectoredExceptionHandler(1, &E3VectoredExceptionHandler);
    if (diagnostic_veh == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_VEH_INSTALL");
    }
    const HMODULE module_base = GetModuleHandleW(nullptr);
    std::fprintf(stderr, "IMP008B_E3_MODULE_BASE=%p\n", module_base);
    std::fflush(stderr);
    Trace("IMP008B_E3_VEH_INSTALLED");

    const std::size_t mapped_code_size = PageAlign(InitialImageSize + patch_size);
    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    Trace("IMP008B_E3_PROCESS_LOAD_BEGIN");
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, mapped_code_size, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_PROCESS_LOAD");
    }
    Trace("IMP008B_E3_PROCESS_LOAD_DONE");
    std::cout << "IMP008B_E3_REAL_PROCESS=PASS\n" << std::flush;

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    const std::size_t image_size_before_relocate = code_set.memory.size();
    Trace("IMP008B_E3_RELOCATE_BEGIN");
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                 &process->GetPostHandlers())) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_RELOCATE");
    }
    Trace("IMP008B_E3_RELOCATE_DONE");

    auto& patch_segment = code_set.PatchSegment();
    patch_segment.offset = image_size_before_relocate;
    patch_segment.addr = Kernel::KProcessAddress{image_size_before_relocate};
    patch_segment.size = static_cast<u32>(patch_size);

    Trace("IMP008B_E3_LOAD_MODULE_BEGIN");
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008B_E3_LOAD_MODULE_DONE");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_THREAD_CREATE");
    }
    Trace("IMP008B_E3_THREAD_CREATED");
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_THREAD_OWNER");
    }
    Trace("IMP008B_E3_THREAD_INIT_DONE");
    std::cout << "IMP008B_E3_REAL_KTHREAD=PASS\n" << std::flush;

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_INTERFACE_NULL");
    }

    const u64 guest_pc = load_base_u64 + GuestCodeOffset;
    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;

    Kernel::Svc::ThreadContext context{};
    context.r[0] = 0x41;
    context.sp = guest_sp;
    context.pc = guest_pc;
    context.pstate = 0;
    Trace("IMP008B_E3_CONTEXT_SET_BEGIN");
    interface->SetContext(context);
    interface->SetTpidrroEl0(0);
    interface->Initialize();
    interface->ClearInstructionCache();
    Trace("IMP008B_E3_CONTEXT_SET_DONE");

    std::fprintf(stderr, "IMP008B_E3_LOAD_BASE=0x%llX\n",
                 static_cast<unsigned long long>(load_base_u64));
    std::fprintf(stderr, "IMP008B_E3_GUEST_PC=0x%llX\n",
                 static_cast<unsigned long long>(guest_pc));
    std::fprintf(stderr, "IMP008B_E3_GUEST_SP=0x%llX\n",
                 static_cast<unsigned long long>(guest_sp));
    std::fflush(stderr);

    // Preserve the verified E2 first-SVC contract exactly: x0 0x41 -> guest add #1 -> SVC #0x33,
    // returning x0 0x42 at the first post-SVC PC with the original SP.
    std::cout << "IMP008B_E3_PRE_FIRST_RUNTHREAD=PASS\n" << std::flush;
    interface->LockThread(thread);
    const Core::HaltReason first_halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    std::cout << "IMP008B_E3_FIRST_RUNTHREAD_RETURNED=PASS\n" << std::flush;

    if (!True(first_halt_reason & Core::HaltReason::SupervisorCall)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_FIRST_HALT_REASON");
    }
    if (interface->GetSvcNumber() != 0x33) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_FIRST_SVC_NUMBER");
    }

    Kernel::Svc::ThreadContext first_returned{};
    interface->GetContext(first_returned);
    if (first_returned.r[0] != 0x42) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_FIRST_GUEST_EXECUTED");
    }
    if (first_returned.pc != load_base_u64 + GuestAfterFirstSvcOffset) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_FIRST_RETURN_PC");
    }
    if (first_returned.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_FIRST_RETURN_SP");
    }
    std::cout << "IMP008B_E3_FIRST_SVC_RETURN=PASS\n";
    std::cout << "IMP008B_E3_FIRST_CONTEXT_COHERENT=PASS\n" << std::flush;

    // E3's single new causal variable: edit the returned architectural x0 on the host, then feed
    // that same context back into the same process-owned ArmNce and KThread for one real re-entry.
    first_returned.r[0] = HostEditedX0;
    interface->SetContext(first_returned);

    Kernel::Svc::ThreadContext edited{};
    interface->GetContext(edited);
    if (edited.r[0] != HostEditedX0 ||
        edited.pc != load_base_u64 + GuestAfterFirstSvcOffset || edited.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_HOST_CONTEXT_EDIT");
    }
    if (thread->GetOwnerProcess() != process) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_SAME_THREAD_OWNER");
    }
    std::cout << "IMP008B_E3_HOST_CONTEXT_EDIT=PASS\n";
    std::cout << "IMP008B_E3_SAME_KTHREAD=PASS\n" << std::flush;

    std::cout << "IMP008B_E3_PRE_SECOND_RUNTHREAD=PASS\n" << std::flush;
    interface->LockThread(thread);
    const Core::HaltReason second_halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    std::cout << "IMP008B_E3_SECOND_RUNTHREAD_RETURNED=PASS\n" << std::flush;

    if (!True(second_halt_reason & Core::HaltReason::SupervisorCall)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_SECOND_HALT_REASON");
    }
    if (interface->GetSvcNumber() != 0x44) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_SECOND_SVC_NUMBER");
    }

    Kernel::Svc::ThreadContext second_returned{};
    interface->GetContext(second_returned);
    if (second_returned.r[0] != SecondReturnedX0) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_REENTRY_GUEST_EXECUTED");
    }
    if (second_returned.pc != load_base_u64 + GuestAfterSecondSvcOffset) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_SECOND_RETURN_PC");
    }
    if (second_returned.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E3_SECOND_RETURN_SP");
    }

    std::cout << "IMP008B_E3_REENTRY_GUEST_EXECUTED=PASS\n";
    std::cout << "IMP008B_E3_SECOND_SVC_RETURN=PASS\n";
    std::cout << "IMP008B_E3_CONTEXT_COHERENT=PASS\n" << std::flush;

    RemoveVectoredExceptionHandler(diagnostic_veh);
    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    std::cout << "IMP008B_E3_GATE=PASS\n" << std::flush;
    return 0;
#endif
}
