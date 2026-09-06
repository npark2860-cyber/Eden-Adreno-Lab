#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <thread>
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
constexpr std::size_t GuestStoreOffset = 0x28;
constexpr std::size_t GuestLoopAddOffset = 0x2c;
constexpr std::size_t GuestLoopBranchOffset = 0x30;
constexpr u32 GuestMovX0One = 0xD2800020;   // movz x0, #1
constexpr u32 GuestStoreX0X1 = 0xF9000020; // str x0, [x1]
constexpr u32 GuestAddX2One = 0x91000442;  // add x2, x2, #1
constexpr u32 GuestBranchLoop = 0x17FFFFFF; // b -4 -> previous instruction
constexpr u64 InitialX2 = 0x100;

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cout << marker << "=PASS\n" << std::flush;
}

#if defined(_WIN32)
LONG CALLBACK E4VectoredExceptionHandler(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto* const record = exception->ExceptionRecord;
    std::fprintf(stderr, "IMP008B_E4_EXCEPTION_CODE=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionCode));
    std::fprintf(stderr, "IMP008B_E4_EXCEPTION_FLAGS=0x%08lX\n",
                 static_cast<unsigned long>(record->ExceptionFlags));
    std::fprintf(stderr, "IMP008B_E4_EXCEPTION_ADDRESS=%p\n", record->ExceptionAddress);
#if defined(_M_ARM64) || defined(__aarch64__)
    if (exception->ContextRecord != nullptr) {
        std::fprintf(stderr, "IMP008B_E4_EXCEPTION_PC=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Pc));
        std::fprintf(stderr, "IMP008B_E4_EXCEPTION_SP=0x%llX\n",
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
    return Fail("IMP008B_E4_PLATFORM_CONTRACT");
#else
    Trace("IMP008B_E4_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008B_E4_NCE_SETTING");
    }
    Trace("IMP008B_E4_SETTINGS_READY");

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
    words[GuestCodeOffset / sizeof(u32)] = GuestMovX0One;
    words[GuestStoreOffset / sizeof(u32)] = GuestStoreX0X1;
    words[GuestLoopAddOffset / sizeof(u32)] = GuestAddX2One;
    words[GuestLoopBranchOffset / sizeof(u32)] = GuestBranchLoop;
    Trace("IMP008B_E4_CODESET_READY");

    Core::NCE::Patcher patcher;
    Trace("IMP008B_E4_PATCH_BEGIN");
    if (!patcher.PatchText(code_set.memory, code)) {
        return Fail("IMP008B_E4_PATCH_TEXT");
    }
    if (patcher.GetPatchMode() != Core::NCE::PatchMode::PostData) {
        return Fail("IMP008B_E4_PATCH_MODE");
    }
    const std::size_t patch_size = patcher.GetSectionSize();
    if (patch_size == 0) {
        return Fail("IMP008B_E4_PATCH_SIZE");
    }
    Trace("IMP008B_E4_PATCH_READY");

    Core::System system;
    Trace("IMP008B_E4_SYSTEM_INIT_BEGIN");
    system.Initialize();
    Trace("IMP008B_E4_SYSTEM_INIT_DONE");
    auto& kernel = system.Kernel();
    Trace("IMP008B_E4_KERNEL_INIT_BEGIN");
    kernel.Initialize();
    Trace("IMP008B_E4_KERNEL_INIT_DONE");

    auto& direct_buffer = system.DeviceMemory().buffer;
    Trace("IMP008B_E4_DIRECT_MAP_BEGIN");
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    std::fprintf(stderr, "IMP008B_E4_FASTMEM_BASE=0x%llX\n",
                 static_cast<unsigned long long>(fastmem_base));
    std::fflush(stderr);
    Trace("IMP008B_E4_DIRECT_MAP_DONE");

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008B_E4_PROCESS_CREATE");
    }
    Trace("IMP008B_E4_PROCESS_CREATED");

    PVOID diagnostic_veh = AddVectoredExceptionHandler(1, &E4VectoredExceptionHandler);
    if (diagnostic_veh == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_VEH_INSTALL");
    }
    Trace("IMP008B_E4_VEH_INSTALLED");

    const std::size_t mapped_code_size = PageAlign(InitialImageSize + patch_size);
    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    Trace("IMP008B_E4_PROCESS_LOAD_BEGIN");
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, mapped_code_size, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_PROCESS_LOAD");
    }
    Trace("IMP008B_E4_PROCESS_LOAD_DONE");
    Trace("IMP008B_E4_REAL_PROCESS");

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    const std::size_t image_size_before_relocate = code_set.memory.size();
    Trace("IMP008B_E4_RELOCATE_BEGIN");
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{load_base_u64}, code, code_set.memory,
                                 &process->GetPostHandlers())) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_RELOCATE");
    }
    Trace("IMP008B_E4_RELOCATE_DONE");

    auto& patch_segment = code_set.PatchSegment();
    patch_segment.offset = image_size_before_relocate;
    patch_segment.addr = Kernel::KProcessAddress{image_size_before_relocate};
    patch_segment.size = static_cast<u32>(patch_size);

    Trace("IMP008B_E4_LOAD_MODULE_BEGIN");
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008B_E4_LOAD_MODULE_DONE");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_THREAD_CREATE");
    }
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_THREAD_OWNER");
    }
    Trace("IMP008B_E4_REAL_KTHREAD");

    Core::ArmInterface* const interface = process->GetArmInterface(0);
    if (interface == nullptr) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_INTERFACE_NULL");
    }

    const u64 guest_pc = load_base_u64 + GuestCodeOffset;
    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;
    const u64 sentinel_address = load_base_u64 + PageSize;
    auto* const sentinel = reinterpret_cast<volatile u64*>(sentinel_address);
    *sentinel = 0;

    Kernel::Svc::ThreadContext context{};
    context.r[0] = 0;
    context.r[1] = sentinel_address;
    context.r[2] = InitialX2;
    context.sp = guest_sp;
    context.pc = guest_pc;
    context.pstate = 0;
    interface->SetContext(context);
    interface->SetTpidrroEl0(0);
    interface->Initialize();
    interface->ClearInstructionCache();
    Trace("IMP008B_E4_CONTEXT_READY");

    std::fprintf(stderr, "IMP008B_E4_LOAD_BASE=0x%llX\n",
                 static_cast<unsigned long long>(load_base_u64));
    std::fprintf(stderr, "IMP008B_E4_GUEST_PC=0x%llX\n",
                 static_cast<unsigned long long>(guest_pc));
    std::fprintf(stderr, "IMP008B_E4_GUEST_SP=0x%llX\n",
                 static_cast<unsigned long long>(guest_sp));
    std::fprintf(stderr, "IMP008B_E4_SENTINEL=0x%llX\n",
                 static_cast<unsigned long long>(sentinel_address));
    std::fflush(stderr);

    const DWORD target_host_tid = GetCurrentThreadId();
    std::atomic<bool> loop_observed{false};
    std::atomic<bool> signal_returned{false};
    std::atomic<bool> cross_thread_caller{false};

    std::thread interrupter([&] {
        const DWORD caller_tid = GetCurrentThreadId();
        cross_thread_caller.store(caller_tid != target_host_tid, std::memory_order_release);
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        while (*sentinel != 1 && std::chrono::steady_clock::now() < deadline) {
            std::this_thread::yield();
        }

        if (*sentinel == 1) {
            loop_observed.store(true, std::memory_order_release);
            Trace("IMP008B_E4_GUEST_LOOP_LIVE");
        } else {
            std::cerr << "IMP008B_E4_GUEST_LOOP_LIVE=FAIL\n" << std::flush;
        }

        if (caller_tid != target_host_tid) {
            Trace("IMP008B_E4_CROSS_THREAD_CALLER");
        } else {
            std::cerr << "IMP008B_E4_CROSS_THREAD_CALLER=FAIL\n" << std::flush;
        }

        Trace("IMP008B_E4_SIGNALINTERRUPT_CALLED");
        interface->SignalInterrupt(thread);
        signal_returned.store(true, std::memory_order_release);
        Trace("IMP008B_E4_SIGNALINTERRUPT_RETURNED");
    });

    Trace("IMP008B_E4_PRE_RUNTHREAD");
    interface->LockThread(thread);
    const Core::HaltReason halt_reason = interface->RunThread(thread);
    interface->UnlockThread(thread);
    Trace("IMP008B_E4_RUNTHREAD_RETURNED");

    interrupter.join();

    if (!loop_observed.load(std::memory_order_acquire)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_LOOP_NOT_OBSERVED");
    }
    if (!cross_thread_caller.load(std::memory_order_acquire)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_NOT_CROSS_THREAD");
    }
    if (!signal_returned.load(std::memory_order_acquire)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_SIGNAL_NOT_RETURNED");
    }
    if (!True(halt_reason & Core::HaltReason::BreakLoop)) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_HALT_REASON");
    }
    Trace("IMP008B_E4_BREAKLOOP_RETURN");

    Kernel::Svc::ThreadContext returned{};
    interface->GetContext(returned);
    const u64 loop_add_pc = load_base_u64 + GuestLoopAddOffset;
    const u64 loop_branch_pc = load_base_u64 + GuestLoopBranchOffset;
    if (returned.r[0] != 1 || returned.r[1] != sentinel_address || returned.r[2] < InitialX2) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_RETURN_REGISTERS");
    }
    if (returned.sp != guest_sp) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_RETURN_SP");
    }
    if (returned.pc != loop_add_pc && returned.pc != loop_branch_pc) {
        std::fprintf(stderr, "IMP008B_E4_UNEXPECTED_RETURN_PC=0x%llX\n",
                     static_cast<unsigned long long>(returned.pc));
        std::fflush(stderr);
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_RETURN_PC");
    }
    if (*sentinel != 1) {
        RemoveVectoredExceptionHandler(diagnostic_veh);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008B_E4_SENTINEL_COHERENCE");
    }
    Trace("IMP008B_E4_ARCH_CONTEXT_COHERENT");

    RemoveVectoredExceptionHandler(diagnostic_veh);
    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    Trace("IMP008B_E4_GATE");
    return 0;
#endif
}
