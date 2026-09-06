#include <atomic>
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
constexpr u64 FaultSearchOffset = 0x100000;
constexpr u64 FaultSearchLimit = 0x2000000;
constexpr u32 BranchX2Instruction = 0xD61F0040U;
constexpr u64 X0Sentinel = 0x1122334455667788ULL;
constexpr u64 X1Sentinel = 0x8877665544332211ULL;
constexpr u64 X18Sentinel = 0x123456789ABC0000ULL;

std::atomic<u32> g_fault_seen{};
std::atomic<u64> g_fault_access_type{};
std::atomic<u64> g_fault_address{};
std::atomic<u64> g_exception_pc{};
std::atomic<u64> g_exception_sp{};

int Fail(const char* marker) {
    std::cerr << marker << "=FAIL\n" << std::flush;
    return 1;
}

void Trace(const char* marker) {
    std::cout << marker << "=PASS\n" << std::flush;
}

#if defined(_WIN32)
LONG CALLBACK C1ObservationVeh(EXCEPTION_POINTERS* exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    const auto& record = *exception->ExceptionRecord;
    if (record.ExceptionCode != EXCEPTION_ACCESS_VIOLATION || record.NumberParameters < 2) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    u32 expected = 0;
    if (g_fault_seen.compare_exchange_strong(expected, 1, std::memory_order_acq_rel)) {
        g_fault_access_type.store(static_cast<u64>(record.ExceptionInformation[0]),
                                  std::memory_order_release);
        g_fault_address.store(static_cast<u64>(record.ExceptionInformation[1]),
                              std::memory_order_release);
        g_exception_pc.store(static_cast<u64>(exception->ContextRecord->Pc),
                             std::memory_order_release);
        g_exception_sp.store(static_cast<u64>(exception->ContextRecord->Sp),
                             std::memory_order_release);

        std::fprintf(stderr, "IMP008C_C1_EXCEPTION_CODE=0x%08lX\n",
                     static_cast<unsigned long>(record.ExceptionCode));
        std::fprintf(stderr, "IMP008C_C1_EXCEPTION_ACCESS=%llu\n",
                     static_cast<unsigned long long>(record.ExceptionInformation[0]));
        std::fprintf(stderr, "IMP008C_C1_EXCEPTION_FAULT=0x%llX\n",
                     static_cast<unsigned long long>(record.ExceptionInformation[1]));
        std::fprintf(stderr, "IMP008C_C1_EXCEPTION_PC=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Pc));
        std::fprintf(stderr, "IMP008C_C1_EXCEPTION_SP=0x%llX\n",
                     static_cast<unsigned long long>(exception->ContextRecord->Sp));
        std::fflush(stderr);
    }

    // Observation only. Production NCE VEH owns the actual fault decision.
    return EXCEPTION_CONTINUE_SEARCH;
}

u64 ReadPhysicalX18() {
    u64 value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

bool IsExecutableProtect(DWORD protect) {
    const DWORD base = protect & 0xFF;
    return base == PAGE_EXECUTE || base == PAGE_EXECUTE_READ ||
           base == PAGE_EXECUTE_READWRITE || base == PAGE_EXECUTE_WRITECOPY;
}

bool IsKnownFaultPc(u64 address, MEMORY_BASIC_INFORMATION& mbi) {
    if (VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi)) == 0) {
        return false;
    }
    if (mbi.State != MEM_COMMIT) {
        return true;
    }
    return !IsExecutableProtect(mbi.Protect);
}
#endif

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    return Fail("IMP008C_C1_PLATFORM_CONTRACT");
#else
    Trace("IMP008C_C1_MAIN_ENTER");

    Settings::values.use_multi_core.SetValue(false);
    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);
    if (!Settings::IsNceEnabled()) {
        return Fail("IMP008C_C1_NCE_SETTING");
    }
    Trace("IMP008C_C1_NCE_ENABLED");

    Core::System system;
    system.Initialize();
    auto& kernel = system.Kernel();
    kernel.Initialize();

    auto& direct_buffer = system.DeviceMemory().buffer;
    direct_buffer.EnableDirectMappedAddress();
    const u64 fastmem_base = reinterpret_cast<u64>(direct_buffer.VirtualBasePointer());
    if (fastmem_base == 0) {
        kernel.Shutdown();
        return Fail("IMP008C_C1_DIRECT_MAP");
    }
    Trace("IMP008C_C1_DIRECT_MAP");

    Kernel::CodeSet code_set;
    code_set.memory.resize(InitialImageSize);
    code_set.memory[0] = static_cast<u8>(BranchX2Instruction & 0xFFU);
    code_set.memory[1] = static_cast<u8>((BranchX2Instruction >> 8) & 0xFFU);
    code_set.memory[2] = static_cast<u8>((BranchX2Instruction >> 16) & 0xFFU);
    code_set.memory[3] = static_cast<u8>((BranchX2Instruction >> 24) & 0xFFU);
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

    auto* process = Kernel::KProcess::Create(kernel);
    if (process == nullptr) {
        kernel.Shutdown();
        return Fail("IMP008C_C1_PROCESS_CREATE");
    }

    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    const Result load_result = process->LoadFromMetadata(
        kernel, metadata, InitialImageSize, Kernel::KProcessAddress{fastmem_base}, 0);
    if (load_result.IsFailure() || !process->IsApplication() || !process->Is64Bit()) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_PROCESS_LOAD");
    }
    Trace("IMP008C_C1_REAL_APPLICATION_PROCESS");

    const auto load_base = process->GetEntryPoint();
    const u64 load_base_u64 = GetInteger(load_base);
    process->LoadModule(kernel, std::move(code_set), load_base);
    Trace("IMP008C_C1_MODULE_LOADED");

    auto* thread = Kernel::KThread::Create(kernel);
    if (thread == nullptr) {
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_THREAD_CREATE");
    }
    const Result thread_result = Kernel::KThread::InitializeDummyThread(system, thread, process);
    if (thread_result.IsFailure() || thread->GetOwnerProcess() != process) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_THREAD_OWNER");
    }
    Trace("IMP008C_C1_REAL_KTHREAD");

    Core::ArmInterface* const arm = process->GetArmInterface(0);
    if (arm == nullptr) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_INTERFACE_NULL");
    }

    // Preserve the E1 no-RTTI production signature for proving that this real process owns ArmNce.
    auto& native = thread->GetNativeExecutionParameters();
    if (native.lock.load(std::memory_order_acquire) != 1) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_LOCK_INITIAL");
    }
    arm->LockThread(thread);
    const bool locked_by_nce = native.lock.load(std::memory_order_acquire) == 0;
    arm->UnlockThread(thread);
    const bool unlocked_by_nce = native.lock.load(std::memory_order_acquire) == 1;
    if (!locked_by_nce || !unlocked_by_nce) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_NCE_SELECTION");
    }
    Trace("IMP008C_C1_NCE_SELECTED");

    const u64 guest_sp = load_base_u64 + InitialImageSize - 0x20;
    u64 fault_pc = 0;
    MEMORY_BASIC_INFORMATION fault_mbi{};
    for (u64 offset = FaultSearchOffset; offset < FaultSearchLimit; offset += PageSize) {
        MEMORY_BASIC_INFORMATION candidate{};
        const u64 address = load_base_u64 + offset;
        if (IsKnownFaultPc(address, candidate)) {
            fault_pc = address;
            fault_mbi = candidate;
            break;
        }
    }
    if (fault_pc == 0) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_FAULT_PC_DISCOVERY");
    }

    std::fprintf(stderr,
                 "IMP008C_C1_FAULT_PC=0x%llX STATE=0x%lX PROTECT=0x%lX BASE=%p ALLOC=%p\n",
                 static_cast<unsigned long long>(fault_pc),
                 static_cast<unsigned long>(fault_mbi.State),
                 static_cast<unsigned long>(fault_mbi.Protect), fault_mbi.BaseAddress,
                 fault_mbi.AllocationBase);
    std::fprintf(stderr, "IMP008C_C1_GUEST_SP=0x%llX\n",
                 static_cast<unsigned long long>(guest_sp));
    std::fprintf(stderr, "IMP008C_C1_ENTRY_PC=0x%llX BRANCH_TARGET=0x%llX\n",
                 static_cast<unsigned long long>(load_base_u64),
                 static_cast<unsigned long long>(fault_pc));
    std::fflush(stderr);
    Trace("IMP008C_C1_NONEXEC_FAULT_PC");

    Kernel::Svc::ThreadContext context{};
    context.r[0] = X0Sentinel;
    context.r[1] = X1Sentinel;
    context.r[2] = fault_pc;
    context.r[18] = X18Sentinel;
    context.sp = guest_sp;
    context.pc = load_base_u64;
    context.pstate = 0;
    arm->SetContext(context);
    arm->SetTpidrroEl0(0);
    arm->Initialize();
    arm->ClearInstructionCache();

    const u64 teb = reinterpret_cast<u64>(NtCurrentTeb());
    const u64 physical_x18_before = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008C_C1_TEB=0x%llX\n", static_cast<unsigned long long>(teb));
    std::fprintf(stderr, "IMP008C_C1_PHYSICAL_X18_BEFORE=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_before));
    std::fflush(stderr);
    if (teb == 0 || physical_x18_before != teb) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_PHYSICAL_X18_TEB_BEFORE");
    }
    Trace("IMP008C_C1_PHYSICAL_X18_TEB_BEFORE");

    PVOID observation_veh = AddVectoredExceptionHandler(1, &C1ObservationVeh);
    if (observation_veh == nullptr) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_OBSERVATION_VEH");
    }

    Trace("IMP008C_C1_PRE_RUNTHREAD");
    arm->LockThread(thread);
    const Core::HaltReason halt_reason = arm->RunThread(thread);
    arm->UnlockThread(thread);
    RemoveVectoredExceptionHandler(observation_veh);
    Trace("IMP008C_C1_RUNTHREAD_RETURNED");

    const u64 physical_x18_after = ReadPhysicalX18();
    std::fprintf(stderr, "IMP008C_C1_PHYSICAL_X18_AFTER=0x%llX\n",
                 static_cast<unsigned long long>(physical_x18_after));
    std::fflush(stderr);

    if (g_fault_seen.load(std::memory_order_acquire) != 1 ||
        g_fault_access_type.load(std::memory_order_acquire) != 8 ||
        g_fault_address.load(std::memory_order_acquire) != fault_pc ||
        g_exception_pc.load(std::memory_order_acquire) != fault_pc ||
        g_exception_sp.load(std::memory_order_acquire) != guest_sp) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_EXECUTE_AV");
    }
    Trace("IMP008C_C1_EXECUTE_AV");

    if (halt_reason != Core::HaltReason::PrefetchAbort) {
        std::fprintf(stderr, "IMP008C_C1_HALT_REASON=0x%llX\n",
                     static_cast<unsigned long long>(halt_reason));
        std::fflush(stderr);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_PREFETCH_ABORT_RETURN");
    }
    Trace("IMP008C_C1_PREFETCH_ABORT_RETURN");

    Kernel::Svc::ThreadContext returned{};
    arm->GetContext(returned);
    if (returned.pc != fault_pc || returned.sp != guest_sp || returned.r[0] != X0Sentinel ||
        returned.r[1] != X1Sentinel || returned.r[18] != X18Sentinel) {
        std::fprintf(stderr,
                     "IMP008C_C1_RETURNED PC=0x%llX SP=0x%llX X0=0x%llX X1=0x%llX X18=0x%llX\n",
                     static_cast<unsigned long long>(returned.pc),
                     static_cast<unsigned long long>(returned.sp),
                     static_cast<unsigned long long>(returned.r[0]),
                     static_cast<unsigned long long>(returned.r[1]),
                     static_cast<unsigned long long>(returned.r[18]));
        std::fflush(stderr);
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_CONTEXT_COHERENT");
    }
    Trace("IMP008C_C1_CONTEXT_COHERENT");

    if (physical_x18_after != teb) {
        thread->Close(kernel);
        process->Close(kernel);
        kernel.Shutdown();
        return Fail("IMP008C_C1_PHYSICAL_X18_TEB_AFTER");
    }
    Trace("IMP008C_C1_PHYSICAL_X18_TEB_AFTER");

    thread->Close(kernel);
    process->Close(kernel);
    kernel.Shutdown();

    Trace("IMP008C_C1_GATE");
    return 0;
#endif
}
