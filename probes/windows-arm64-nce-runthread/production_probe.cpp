#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>

#include "common/settings.h"
#include "core/arm/dynarmic/arm_dynarmic_64.h"
#include "core/arm/nce/arm_nce.h"
#include "core/arm/nce/instructions.h"
#include "core/arm/nce/patcher.h"
#include "core/core.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_scoped_resource_reservation.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/kernel.h"
#include "core/memory.h"

using Core::HaltReason;
using Core::NCE::PatchMode;
using Core::NCE::Patcher;
using Core::NCE::SVC;

namespace {

constexpr std::size_t ImageSize = 0x100;
constexpr std::size_t AllocationSize = 0x20000;
constexpr std::size_t EntryOffset = 0x24;
constexpr std::size_t GuestStackSize = 0x10000;
constexpr std::size_t BreakLoopOffset = 0x1F000;

constexpr std::uint32_t Svc6 = 0xD40000C1u;
constexpr std::uint32_t Svc7 = 0xD40000E1u;
constexpr std::uint32_t Brk = 0xD4200000u;
constexpr std::uint32_t BranchSelf = 0x14000000u;
constexpr std::uint32_t SpinLockUnlocked = 1;

static_assert(SVC{Svc6}.Verify() && SVC{Svc6}.GetValue() == 6);
static_assert(SVC{Svc7}.Verify() && SVC{Svc7}.GetValue() == 7);

constexpr std::uint64_t InitialX0 = 0x1010101010101010ull;
constexpr std::uint64_t InitialX16 = 0x1616161616161616ull;
constexpr std::uint64_t InitialX17 = 0x1717171717171717ull;
constexpr std::uint64_t InitialX18 = 0x1818181818181818ull;
constexpr std::uint64_t ResumeX0 = 0xA0A0A0A0A0A0A0A0ull;
constexpr std::uint64_t ResumeX16 = 0x2626262626262626ull;
constexpr std::uint64_t ResumeX17 = 0x2727272727272727ull;
constexpr std::uint64_t ResumeX18 = 0x2828282828282828ull;
constexpr std::uint64_t BreakX0 = 0xB0B0B0B0B0B0B0B0ull;
constexpr std::uint64_t BreakX18 = 0x3838383838383838ull;

std::uint64_t ReadPhysicalX18() {
    std::uint64_t value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

bool HasReason(HaltReason value, HaltReason reason) {
    return True(value & reason);
}

void Report(const char* name, bool pass) {
    std::printf("%s=%s\n", name, pass ? "PASS" : "FAIL");
}

struct Allocation {
    std::uint8_t* base{};

    ~Allocation() {
        if (base != nullptr) {
            VirtualFree(base, 0, MEM_RELEASE);
        }
    }
};

struct KernelObjects {
    Core::System system;
    Kernel::KProcess* process{};
    Kernel::KThread* thread{};

    ~KernelObjects() {
        auto& kernel = system.Kernel();
        if (thread != nullptr) {
            thread->Close(kernel);
            thread = nullptr;
        }
        if (process != nullptr) {
            process->Close(kernel);
            process = nullptr;
        }
        kernel.Shutdown();
    }
};

bool BuildRealNceProcess(KernelObjects& objects) {
    objects.system.Initialize();
    auto& kernel = objects.system.Kernel();
    kernel.Initialize();

    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true); // true means the controlled program is 39-bit.
    if (!Settings::IsNceEnabled()) {
        return false;
    }

    const auto metadata = FileSys::ProgramMetadata::GetDefault();
    objects.process = Kernel::KProcess::Create(kernel);
    if (objects.process == nullptr) {
        return false;
    }
    Kernel::KProcess::Register(kernel, objects.process);

    if (!objects.process
             ->LoadFromMetadata(kernel, metadata, Core::Memory::YUZU_PAGESIZE,
                                Kernel::KProcessAddress{}, 0)
             .IsSuccess()) {
        return false;
    }

    Kernel::KScopedResourceReservation thread_reservation(
        kernel, objects.process, Kernel::Svc::LimitableResource::ThreadCountMax);
    if (!thread_reservation.Succeeded()) {
        return false;
    }

    objects.thread = Kernel::KThread::Create(kernel);
    if (objects.thread == nullptr ||
        !Kernel::KThread::InitializeDummyThread(objects.system, objects.thread, objects.process)
             .IsSuccess()) {
        return false;
    }
    thread_reservation.Commit();
    Kernel::KThread::Register(kernel, objects.thread);

    return true;
}

} // namespace

int main() {
    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    const bool x18_before = ReadPhysicalX18() == teb;

    KernelObjects objects;
    if (!BuildRealNceProcess(objects)) {
        Report("IMP008B_REAL_KERNEL_PROCESS_THREAD", false);
        return 1;
    }

    auto& kernel = objects.system.Kernel();
    auto* const process = objects.process;
    auto* const thread = objects.thread;
    auto* const interface = process->GetArmInterface(3);

    const bool nce_selection_ok = dynamic_cast<Core::ArmNce*>(interface) != nullptr;
    const bool owner_ok = thread->GetOwnerProcess() == process;
    Report("IMP008B_REAL_KPROCESS_ARMNCE_SELECTION", nce_selection_ok);
    Report("IMP008B_REAL_KTHREAD_OWNER", owner_ok);
    if (!nce_selection_ok || !owner_ok) {
        return 1;
    }

    std::vector<std::uint8_t> image(ImageSize, 0);
    auto* words = reinterpret_cast<std::uint32_t*>(image.data());
    words[EntryOffset / 4] = Svc6;
    words[EntryOffset / 4 + 1] = Svc7;
    words[EntryOffset / 4 + 2] = Brk;

    Kernel::CodeSet::Segment code{};
    code.offset = 0;
    code.addr = Common::ProcessAddress{0};
    code.size = static_cast<std::uint32_t>(ImageSize);

    Patcher patcher;
    const bool patch_ok = patcher.PatchText(image, code);
    const bool mode_ok = patch_ok && patcher.GetPatchMode() == PatchMode::PostData;

    Allocation allocation;
    allocation.base = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, AllocationSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (allocation.base == nullptr || !mode_ok) {
        Report("IMP008B_PATCH_MODE", mode_ok);
        return 1;
    }

    Allocation guest_stack;
    guest_stack.base = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, GuestStackSize, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (guest_stack.base == nullptr) {
        Report("IMP008B_GUEST_STACK_ALLOCATION", false);
        return 1;
    }

    const bool relocate_ok = patcher.RelocateAndCopy(
        Common::ProcessAddress{reinterpret_cast<std::uintptr_t>(allocation.base)}, code, image,
        &process->GetPostHandlers());
    if (!relocate_ok || image.size() >= BreakLoopOffset) {
        Report("IMP008B_PATCH_RELOCATE", false);
        return 1;
    }

    std::memcpy(allocation.base, image.data(), image.size());
    *reinterpret_cast<std::uint32_t*>(allocation.base + BreakLoopOffset) = BranchSelf;
    if (!FlushInstructionCache(GetCurrentProcess(), allocation.base, AllocationSize)) {
        Report("IMP008B_FLUSH_ICACHE", false);
        return 1;
    }

    const auto first_svc_pc = reinterpret_cast<std::uintptr_t>(allocation.base) + EntryOffset;
    const auto second_svc_pc = first_svc_pc + 4;
    const auto break_loop_pc =
        reinterpret_cast<std::uintptr_t>(allocation.base) + BreakLoopOffset;
    const bool post_handler_ok = process->GetPostHandlers().contains(second_svc_pc);

    const auto guest_stack_top =
        reinterpret_cast<std::uintptr_t>(guest_stack.base + GuestStackSize) & ~std::uintptr_t{0xF};

    interface->Initialize();

    auto& ctx = thread->GetContext();
    ctx = {};
    ctx.sp = guest_stack_top;
    ctx.pc = first_svc_pc;
    ctx.r[0] = InitialX0;
    ctx.r[16] = InitialX16;
    ctx.r[17] = InitialX17;
    ctx.r[18] = InitialX18;

    interface->SetContext(ctx);
    interface->SetTpidrroEl0(GetInteger(thread->GetTlsAddress()));
    interface->SetWatchpointArray(&process->GetWatchpoints());

    interface->LockThread(thread);
    const auto first_hr = interface->RunThread(thread);
    interface->UnlockThread(thread);
    interface->GetContext(ctx);

    const bool first_return_ok = HasReason(first_hr, HaltReason::SupervisorCall);
    const bool first_svc_ok = interface->GetSvcNumber() == 6;
    const bool first_pc_ok = ctx.pc == second_svc_pc;
    const bool first_x0_ok = ctx.r[0] == InitialX0;
    const bool first_x16_ok = ctx.r[16] == InitialX16;
    const bool first_x17_ok = ctx.r[17] == InitialX17;
    const bool first_x18_ok = ctx.r[18] == InitialX18;
    const auto& first_params = thread->GetNativeExecutionParameters();
    const bool first_lifecycle_ok = !first_params.is_running && first_params.native_context == nullptr &&
                                    first_params.lock.load(std::memory_order_acquire) == SpinLockUnlocked;

    ctx.r[0] = ResumeX0;
    ctx.r[16] = ResumeX16;
    ctx.r[17] = ResumeX17;
    ctx.r[18] = ResumeX18;
    interface->SetContext(ctx);

    interface->LockThread(thread);
    const auto second_hr = interface->RunThread(thread);
    interface->UnlockThread(thread);
    interface->GetContext(ctx);

    const bool second_return_ok = HasReason(second_hr, HaltReason::SupervisorCall);
    const bool second_svc_ok = interface->GetSvcNumber() == 7;
    const bool resumed_x0_ok = ctx.r[0] == ResumeX0;
    const bool resumed_x16_ok = ctx.r[16] == ResumeX16;
    const bool resumed_x17_ok = ctx.r[17] == ResumeX17;
    const bool resumed_x18_ok = ctx.r[18] == ResumeX18;
    const auto& second_params = thread->GetNativeExecutionParameters();
    const bool second_lifecycle_ok = !second_params.is_running && second_params.native_context == nullptr &&
                                     second_params.lock.load(std::memory_order_acquire) == SpinLockUnlocked;

    ctx.pc = break_loop_pc;
    ctx.sp = guest_stack_top;
    ctx.r[0] = BreakX0;
    ctx.r[18] = BreakX18;
    interface->SetContext(ctx);

    std::atomic<bool> interrupt_called{false};
    std::thread breaker([&] {
        auto& params = thread->GetNativeExecutionParameters();
        while (!params.is_running) {
            std::this_thread::yield();
        }
        interface->SignalInterrupt(thread);
        interrupt_called.store(true, std::memory_order_release);
    });

    interface->LockThread(thread);
    const auto break_hr = interface->RunThread(thread);
    interface->UnlockThread(thread);
    breaker.join();
    interface->GetContext(ctx);

    const bool break_return_ok = HasReason(break_hr, HaltReason::BreakLoop);
    const bool break_called_ok = interrupt_called.load(std::memory_order_acquire);
    const bool break_pc_ok = ctx.pc == break_loop_pc;
    const bool break_sp_ok = ctx.sp == guest_stack_top;
    const bool break_x0_ok = ctx.r[0] == BreakX0;
    const bool break_x18_ok = ctx.r[18] == BreakX18;
    const auto& break_params = thread->GetNativeExecutionParameters();
    const bool break_lifecycle_ok = !break_params.is_running && break_params.native_context == nullptr &&
                                    break_params.lock.load(std::memory_order_acquire) == SpinLockUnlocked;

    const bool x18_after_nce = ReadPhysicalX18() == teb;

    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Dynarmic);
    Settings::SetNceEnabled(true); // still a 39-bit control process; backend selection disables NCE.
    const bool nce_disabled_for_control = !Settings::IsNceEnabled();

    auto* control_process = Kernel::KProcess::Create(kernel);
    bool dynarmic_control_ok = false;
    if (control_process != nullptr) {
        Kernel::KProcess::Register(kernel, control_process);
        const auto metadata = FileSys::ProgramMetadata::GetDefault();
        if (control_process
                ->LoadFromMetadata(kernel, metadata, Core::Memory::YUZU_PAGESIZE,
                                   Kernel::KProcessAddress{}, 0)
                .IsSuccess()) {
            dynarmic_control_ok =
                dynamic_cast<Core::ArmDynarmic64*>(control_process->GetArmInterface(3)) != nullptr;
        }
        control_process->Close(kernel);
    }

    Settings::values.cpu_backend.SetValue(Settings::CpuBackend::Nce);
    Settings::SetNceEnabled(true);

    const bool x18_after_control = ReadPhysicalX18() == teb;

    Report("IMP008B_REAL_KERNEL_PROCESS_THREAD", true);
    Report("IMP008B_GUEST_STACK_ALLOCATION", true);
    Report("IMP008B_PATCH_MODE", mode_ok);
    Report("IMP008B_PATCH_RELOCATE", relocate_ok);
    Report("IMP008B_PROCESS_POST_HANDLER_MAP", post_handler_ok);
    Report("IMP008B_FIRST_RUNTHREAD_SVC_RETURN", first_return_ok);
    Report("IMP008B_FIRST_SVC_ID", first_svc_ok);
    Report("IMP008B_FIRST_SVC_NEXT_PC", first_pc_ok);
    Report("IMP008B_FIRST_X0", first_x0_ok);
    Report("IMP008B_FIRST_X16", first_x16_ok);
    Report("IMP008B_FIRST_X17", first_x17_ok);
    Report("IMP008B_FIRST_VIRTUAL_X18", first_x18_ok);
    Report("IMP008B_FIRST_LOCK_LIFECYCLE", first_lifecycle_ok);
    Report("IMP008B_SECOND_RUNTHREAD_SVC_RETURN", second_return_ok);
    Report("IMP008B_SECOND_SVC_ID", second_svc_ok);
    Report("IMP008B_RESUME_X0", resumed_x0_ok);
    Report("IMP008B_RESUME_X16", resumed_x16_ok);
    Report("IMP008B_RESUME_X17", resumed_x17_ok);
    Report("IMP008B_RESUME_VIRTUAL_X18", resumed_x18_ok);
    Report("IMP008B_SECOND_LOCK_LIFECYCLE", second_lifecycle_ok);
    Report("IMP008B_SIGNALINTERRUPT_CALLED", break_called_ok);
    Report("IMP008B_BREAKLOOP_RETURN", break_return_ok);
    Report("IMP008B_BREAK_ARCH_PC", break_pc_ok);
    Report("IMP008B_BREAK_ARCH_SP", break_sp_ok);
    Report("IMP008B_BREAK_X0", break_x0_ok);
    Report("IMP008B_BREAK_VIRTUAL_X18", break_x18_ok);
    Report("IMP008B_BREAK_LOCK_LIFECYCLE", break_lifecycle_ok);
    Report("IMP008B_PHYSICAL_X18_TEB_BEFORE", x18_before);
    Report("IMP008B_PHYSICAL_X18_TEB_AFTER_NCE", x18_after_nce);
    Report("IMP008B_DYNARMIC_CONTROL_NCE_DISABLED", nce_disabled_for_control);
    Report("IMP008B_DYNARMIC_CONTROL_SELECTED", dynarmic_control_ok);
    Report("IMP008B_PHYSICAL_X18_TEB_AFTER_CONTROL", x18_after_control);

    const bool pass = x18_before && nce_selection_ok && owner_ok && patch_ok && mode_ok && relocate_ok &&
                      post_handler_ok && first_return_ok && first_svc_ok && first_pc_ok && first_x0_ok &&
                      first_x16_ok && first_x17_ok && first_x18_ok && first_lifecycle_ok &&
                      second_return_ok && second_svc_ok && resumed_x0_ok && resumed_x16_ok &&
                      resumed_x17_ok && resumed_x18_ok && second_lifecycle_ok && break_called_ok &&
                      break_return_ok && break_pc_ok && break_sp_ok && break_x0_ok && break_x18_ok &&
                      break_lifecycle_ok && x18_after_nce && nce_disabled_for_control &&
                      dynarmic_control_ok && x18_after_control;

    std::printf("IMP008B_WINDOWS_REAL_RUNTHREAD_SVC_BREAK_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
