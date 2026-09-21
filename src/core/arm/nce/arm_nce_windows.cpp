// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#if !defined(_WIN32)
#error arm_nce_windows.cpp is only available on Windows.
#endif

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <thread>
#include <utility>

#include "common/host_memory_windows_lease.h"
#include "core/arm/nce/arm_nce.h"
#include "core/arm/nce/arm_nce_asm_definitions.h"
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_cross_thread_break.h"
#include "core/arm/nce/windows_exception_context.h"
#include "core/arm/nce/windows_nce_transition.h"
#include "core/arm/nce/windows_patch_code_metadata.h"
#include "core/arm/nce/windows_x18_fallback_runner.h"
#include "core/arm/nce/windows_x18_fallback_trap.h"
#include "core/core.h"
#include "core/device_memory.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/svc_types.h"
#include "core/memory.h"

namespace Core {

extern "C" void WindowsNceGuestStackBridge() noexcept;
extern "C" void WindowsNceHostStackBridge() noexcept;
extern "C" void WindowsNceV74HostStackBridge() noexcept;
extern "C" void WindowsNceV74HostReturnProbe() noexcept;

namespace {

constexpr u64 V74ProvenanceMagicBase = 0x56373450524F0000ULL;

using NativeExecutionParameters = Kernel::KThread::NativeExecutionParameters;

static_assert(offsetof(NativeExecutionParameters, native_context) == TpidrEl0NativeContext);
static_assert(offsetof(NativeExecutionParameters, lock) == TpidrEl0Lock);
static_assert(offsetof(NativeExecutionParameters, magic) == TpidrEl0TlsMagic);

std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

struct WindowsTebStackBounds {
    NT_TIB* tib{};
    void* host_stack_base{};
    void* host_stack_limit{};
};

static_assert(offsetof(NT_TIB, StackBase) == 0x08);
static_assert(offsetof(NT_TIB, StackLimit) == 0x10);

[[nodiscard]] bool InstallGuestTebStackBounds(GuestContext& guest,
                                              WindowsTebStackBounds& bounds) noexcept {
    const u64 guest_sp = guest.sp;
    if (guest_sp == 0) {
        return false;
    }

    MEMORY_BASIC_INFORMATION stack_mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(guest_sp - 1), &stack_mbi,
                     sizeof(stack_mbi)) == 0 ||
        stack_mbi.AllocationBase == nullptr) {
        return false;
    }

    const auto allocation_base =
        reinterpret_cast<std::uintptr_t>(stack_mbi.AllocationBase);
    std::uintptr_t allocation_end = allocation_base;
    for (std::uintptr_t cursor = allocation_base;;) {
        MEMORY_BASIC_INFORMATION region{};
        if (VirtualQuery(reinterpret_cast<const void*>(cursor), &region, sizeof(region)) == 0 ||
            region.AllocationBase != stack_mbi.AllocationBase) {
            break;
        }

        const auto region_end = reinterpret_cast<std::uintptr_t>(region.BaseAddress) +
                                static_cast<std::uintptr_t>(region.RegionSize);
        if (region_end <= cursor) {
            break;
        }
        allocation_end = region_end;
        cursor = region_end;
    }

    const auto guest_sp_value = static_cast<std::uintptr_t>(guest_sp);
    // A downward-growing stack may begin with SP exactly at StackBase, which is one-past
    // the highest address in the allocation. VirtualQuery above intentionally probes SP - 1,
    // so accept guest_sp == allocation_end while still rejecting values above the allocation.
    if (guest_sp_value <= allocation_base || guest_sp_value > allocation_end) {
        return false;
    }

    auto* const tib = reinterpret_cast<NT_TIB*>(NtCurrentTeb());
    bounds.tib = tib;
    bounds.host_stack_base = tib->StackBase;
    bounds.host_stack_limit = tib->StackLimit;
    guest.windows_guest_stack_base = static_cast<u64>(allocation_end);
    guest.windows_guest_stack_limit = static_cast<u64>(allocation_base);
    guest.windows_host_stack_base =
        static_cast<u64>(reinterpret_cast<std::uintptr_t>(bounds.host_stack_base));
    guest.windows_host_stack_limit =
        static_cast<u64>(reinterpret_cast<std::uintptr_t>(bounds.host_stack_limit));
    // Keep the host StackLimit through the host-side NtContinue transition. Publishing the guest
    // allocation limit here makes the Windows ARM64 stack probe in ucrtbase run against guest
    // bounds while it still owns the host stack. Only publish the guest StackBase/top at this seam.
    tib->StackBase = reinterpret_cast<void*>(allocation_end);
    return true;
}

void RestoreHostTebStackBounds(WindowsTebStackBounds& bounds) noexcept {
    if (bounds.tib == nullptr) {
        return;
    }
    bounds.tib->StackBase = bounds.host_stack_base;
    bounds.tib->StackLimit = bounds.host_stack_limit;
    bounds.tib = nullptr;
}

[[nodiscard]] bool EnsureWindowsGuestStackLease(
    System& system, Kernel::KProcess* process, u64 guest_sp,
    std::optional<Common::HostMemory::PrivateMappingLease>& stack_lease) {
    if (process == nullptr || guest_sp == 0) {
        LOG_ERROR(Core_ARM, "Windows NCE stack lease received an invalid process or SP");
        return false;
    }

    Kernel::KMemoryInfo guest_stack_info{};
    Kernel::Svc::PageInfo guest_stack_page{};
    const auto guest_stack_query = process->GetPageTable().QueryInfo(
        std::addressof(guest_stack_info), std::addressof(guest_stack_page),
        Kernel::KProcessAddress{guest_sp});
    if (guest_stack_query.IsFailure()) {
        LOG_ERROR(Core_ARM, "Windows NCE guest stack page-table query failed");
        return false;
    }

    const bool guest_sp_is_stack = guest_stack_info.GetState() == Kernel::KMemoryState::Stack;

    MEMORY_BASIC_INFORMATION stack_mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(guest_sp - 1), &stack_mbi,
                     sizeof(stack_mbi)) == 0 ||
        stack_mbi.AllocationBase == nullptr) {
        LOG_ERROR(Core_ARM, "Windows NCE guest stack VirtualQuery failed");
        return false;
    }

    if (stack_lease.has_value()) {
        const bool active_lease_owns_sp = stack_lease->ContainsAddress(guest_sp - 1);
        if (active_lease_owns_sp) {
            if (!guest_sp_is_stack || stack_mbi.Type != MEM_PRIVATE) {
                LOG_ERROR(Core_ARM,
                          "Windows NCE active private stack lease has invalid guest stack state");
                return false;
            }
            return true;
        }

        // Native guest code may switch SP between user-space stacks without leaving the current
        // RunThread epoch. The previous lease still owns a valid dormant stack, but it must be
        // synchronized/restored before evaluating the newly active guest stack. If that stack later
        // becomes active again, it will be leased again from the section-backed mapping.
        if (!stack_lease->Restore()) {
            LOG_ERROR(Core_ARM, "Windows NCE failed to roll over previous private stack lease");
            return false;
        }
        stack_lease.reset();
    }

    // Preserve the V7 eligibility policy: already-private stacks and synthetic/non-Stack mapped
    // probe stacks do not need a lease. Only a real KPageTable Stack backed by MEM_MAPPED does.
    if (stack_mbi.Type == MEM_PRIVATE) {
        return true;
    }
    if (!guest_sp_is_stack && stack_mbi.Type == MEM_MAPPED) {
        return true;
    }
    if (!guest_sp_is_stack || stack_mbi.Type != MEM_MAPPED) {
        LOG_ERROR(Core_ARM, "Windows NCE guest stack has unsupported host backing type/state");
        return false;
    }

    const auto stack_base = reinterpret_cast<std::uintptr_t>(stack_mbi.AllocationBase);
    std::uintptr_t stack_end = stack_base;
    for (std::uintptr_t cursor = stack_base;;) {
        MEMORY_BASIC_INFORMATION region{};
        if (VirtualQuery(reinterpret_cast<const void*>(cursor), &region, sizeof(region)) == 0 ||
            region.AllocationBase != stack_mbi.AllocationBase) {
            break;
        }
        const auto region_end = reinterpret_cast<std::uintptr_t>(region.BaseAddress) +
                                static_cast<std::uintptr_t>(region.RegionSize);
        if (region_end <= cursor) {
            break;
        }
        stack_end = region_end;
        cursor = region_end;
    }

    if (stack_end <= stack_base || guest_sp <= stack_base || guest_sp >= stack_end ||
        (stack_base & Memory::YUZU_PAGEMASK) != 0 ||
        ((stack_end - stack_base) & Memory::YUZU_PAGEMASK) != 0) {
        LOG_ERROR(Core_ARM, "Windows NCE real guest stack host allocation is invalid");
        return false;
    }

    const auto stack_size = static_cast<size_t>(stack_end - stack_base);
    auto* const backing_pointer =
        process->GetMemory().GetPointer(Common::ProcessAddress{stack_base});
    if (backing_pointer == nullptr) {
        LOG_ERROR(Core_ARM, "Windows NCE real guest stack has no backing pointer");
        return false;
    }

    for (size_t offset = 0; offset < stack_size; offset += Memory::YUZU_PAGESIZE) {
        auto* const page_pointer =
            process->GetMemory().GetPointer(Common::ProcessAddress{stack_base + offset});
        if (page_pointer != backing_pointer + offset) {
            LOG_ERROR(Core_ARM, "Windows NCE real guest stack backing is not contiguous");
            return false;
        }
    }

    auto& buffer = system.DeviceMemory().buffer;
    const auto backing_base = reinterpret_cast<std::uintptr_t>(buffer.BackingBasePointer());
    const auto backing_address = reinterpret_cast<std::uintptr_t>(backing_pointer);
    if (backing_address < backing_base) {
        LOG_ERROR(Core_ARM, "Windows NCE real guest stack backing pointer is outside HostMemory");
        return false;
    }
    const auto backing_offset = static_cast<size_t>(backing_address - backing_base);

    auto acquired = buffer.AcquireDirectMappedPrivateLease(
        reinterpret_cast<void*>(stack_base), backing_offset, stack_size,
        Common::MemoryPermission::ReadWrite);
    if (!acquired.has_value()) {
        LOG_ERROR(Core_ARM, "Windows NCE failed to acquire private HostMemory stack lease");
        return false;
    }

    stack_lease.emplace(std::move(*acquired));
    return true;
}

struct BreakTransformState {
    ArmNce* nce{};
    bool transformed{};
    bool host_window{};
    bool patch_window{};
};

bool WindowsBreakTransform(ARM64_NT_CONTEXT& context, void* opaque) noexcept {
    auto* const state = static_cast<BreakTransformState*>(opaque);
    if (state == nullptr || state->nce == nullptr || state->nce->m_windows_break == nullptr) {
        return false;
    }

    // The scheduler lock can become available just before RtlRestoreContext performs the final
    // host-stack -> guest-stack transfer. Never snapshot that transition window as guest state.
    // SignalInterrupt retains the NativeExecutionParameters lock and retries after the target has
    // resumed far enough to own a guest stack.
    if (state->nce->m_windows_break->IsHostStackPointer(context.Sp)) {
        state->host_window = true;
        return false;
    }

    state->host_window = false;
    auto* const thread = state->nce->m_running_thread;
    auto* const process = thread != nullptr ? thread->GetOwnerProcess() : nullptr;
    if (process != nullptr && NCE::WindowsPatchCodeMetadata::Contains(
                                  context.Pc, process->GetPostHandlers())) {
        state->patch_window = true;
        return false;
    }

    state->patch_window = false;

    // A Windows host bridge/helper can transiently execute with the physical guest SP already
    // installed. Stack ownership alone is therefore insufficient to prove that the suspended
    // CONTEXT is guest architectural state. Only snapshot a PC that belongs to the guest process
    // address space; otherwise resume unchanged and let SignalInterrupt retry the host window.
    if (process == nullptr ||
        !process->GetMemory().IsValidVirtualAddressRange(context.Pc, sizeof(u32))) {
        state->host_window = true;
        return false;
    }

    auto& guest = state->nce->m_guest_ctx;
    const auto reason = guest.esr_el1.exchange(0, std::memory_order_acq_rel);
    NCE::WindowsNceTransition::RedirectToHost(context, guest, true, reason);
    state->transformed = true;
    return true;
}

LONG CALLBACK WindowsNceVectoredExceptionHandler(PEXCEPTION_POINTERS exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    auto* const guest = NCE::WindowsExceptionContext::CurrentGuestContext();
    if (guest == nullptr || guest->parent == nullptr || guest->parent->m_running_thread == nullptr) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    auto* const nce = guest->parent;
    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);

    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.
    // Exceptions there belong to Windows/host code and must remain chainable.
    if (nce->m_windows_break != nullptr && nce->m_windows_break->IsHostStackPointer(context.Sp)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    auto* const thread = nce->m_running_thread;
    auto* const process = thread->GetOwnerProcess();
    auto* const params = &thread->GetNativeExecutionParameters();

    // IMP-006 ordinary guest-x18 sites deliberately trap with BRK #0xF000. Once the tagged
    // process-owned metadata confirms the site, transfer ownership of the native-parameter lock
    // back to the host return path and reuse the proven x18 trap/transition seam.
    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&
        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(
            context.Pc, process->GetPostHandlers()).has_value()) {
        params->lock.store(SpinLockLocked, std::memory_order_release);
        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(
            exception, *guest, process->GetPostHandlers());
        if (redirected) {
            context.X[18] = reinterpret_cast<u64>(NtCurrentTeb());
            NCE::WindowsNceTransition::ContinueContext(context);
        }
        params->lock.store(SpinLockUnlocked, std::memory_order_release);
        return EXCEPTION_CONTINUE_SEARCH;
    }

    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT) {
        const bool guest_mapped =
            process->GetMemory().IsValidVirtualAddressRange(context.Pc, sizeof(u32));

        nce->m_windows_diag_unmatched_break_pc.store(context.Pc, std::memory_order_relaxed);
        nce->m_windows_diag_unmatched_break_sp.store(context.Sp, std::memory_order_relaxed);
        nce->m_windows_diag_unmatched_break_lr.store(context.X[30], std::memory_order_relaxed);
        nce->m_windows_diag_unmatched_break_exception_address.store(
            reinterpret_cast<u64>(exception->ExceptionRecord->ExceptionAddress),
            std::memory_order_relaxed);
        nce->m_windows_diag_unmatched_break_guest_mapped.store(
            guest_mapped ? 1ULL : 0ULL, std::memory_order_relaxed);
        nce->m_windows_diag_unmatched_break_seq.fetch_add(1, std::memory_order_release);

        // Diagnostic-only: preserve GuestContext exactly as it was before the unmatched
        // breakpoint. Return through the already-proven host bridge solely to expose the raw
        // Windows CONTEXT from a safe host-side logging seam.
        params->lock.store(SpinLockLocked, std::memory_order_release);
        NCE::WindowsNceTransition::RedirectToHost(
            context, *guest, false, static_cast<u64>(HaltReason::PrefetchAbort));
        context.X[18] = reinterpret_cast<u64>(NtCurrentTeb());
        NCE::WindowsNceTransition::ContinueContext(context);
    }

    if (NCE::WindowsExceptionContext::IsAccessViolation(*exception->ExceptionRecord)) {
        const auto fault_address = reinterpret_cast<u64>(
            NCE::WindowsExceptionContext::GetFaultAddress(*exception->ExceptionRecord));
        nce->m_windows_pending_nce_fault = true;
        nce->m_windows_pending_nce_fault_address = fault_address;
        nce->m_windows_pending_nce_fault_page = fault_address & ~Memory::YUZU_PAGEMASK;
        params->lock.store(SpinLockLocked, std::memory_order_release);
        NCE::WindowsNceTransition::RedirectToHost(
            context, *guest, true, static_cast<u64>(HaltReason::PrefetchAbort));

        // The x18 breakpoint path already uses the proven direct NtContinue transition after
        // RedirectToHost. Do the same for AV recovery instead of returning the mutated CONTEXT to
        // the Windows exception dispatcher. V72 natural dumps showed a reproducible second
        // execute-AV at PC=SP=0 with TEB StackBase/StackLimit=0, exactly matching
        // WindowsNceHostStackBridge executing after its volatile x1/x2/x3/x16 scratch values were
        // lost. Direct NtContinue keeps the redirected register contract intact through resume.
        context.X[18] = reinterpret_cast<u64>(NtCurrentTeb());

        // V74 diagnostic only: prove whether the fully-written AV host-return CONTEXT reaches the
        // first bridge instruction intact. The low 16 bits of x25 encode writer-side validity;
        // x26 carries HostContext only so the diagnostic success trampoline can restore the exact
        // host nonvolatile state. The diagnostic bridge itself copies its raw entry registers into
        // x19-x24/x27-x28 before performing the production bridge operations. If the natural
        // terminal AV recurs, the WER CONTEXT therefore preserves both the writer marker and the
        // consumer-side values without logging or calling host code on the guest stack.
        u64 provenance_flags = 0;
        const u64 submit_stack_base = context.X[1];
        const u64 submit_stack_limit = context.X[2];
        const u64 submit_host_sp = context.X[3];
        const u64 submit_host_pc = context.X[16];
        if (submit_stack_base != 0 && submit_stack_limit != 0 && submit_host_sp != 0 &&
            submit_host_pc != 0) {
            provenance_flags |= 0x0001;
        }
        if (submit_stack_limit < submit_stack_base) {
            provenance_flags |= 0x0002;
        }
        if (submit_host_sp >= submit_stack_limit && submit_host_sp < submit_stack_base) {
            provenance_flags |= 0x0004;
        }
        if ((submit_host_pc & 0x3) == 0 && submit_host_pc != 0) {
            provenance_flags |= 0x0008;
        }
        if (context.X[18] == reinterpret_cast<u64>(NtCurrentTeb())) {
            provenance_flags |= 0x0010;
        }
        if (context.X[30] == submit_host_pc && submit_host_pc != 0) {
            provenance_flags |= 0x0020;
        }

        context.X[25] = V74ProvenanceMagicBase | provenance_flags;
        context.X[26] = reinterpret_cast<u64>(&guest->host_ctx);
        context.X[16] = reinterpret_cast<u64>(&WindowsNceV74HostReturnProbe);
        context.Pc = reinterpret_cast<u64>(&WindowsNceV74HostStackBridge);
        NCE::WindowsNceTransition::ContinueContext(context);
    }

    // IMP-008A does not claim complete game fault compatibility. Unknown host/guest exception
    // classes remain chainable instead of being swallowed by the NCE VEH.
    return EXCEPTION_CONTINUE_SEARCH;
}

} // namespace

ArmNce::ArmNce(System& system, bool uses_wall_clock, std::size_t core_index)
    : ArmInterface{uses_wall_clock}, m_system{system}, m_core_index{core_index},
      m_windows_break{std::make_unique<NCE::WindowsCrossThreadBreak>()} {
    m_guest_ctx.system = &m_system;
}

ArmNce::~ArmNce() = default;

void ArmNce::Initialize() {
    if (!NCE::WindowsNceTransition::Initialize()) {
        LOG_CRITICAL(Core_ARM, "Failed to resolve Windows NCE NtContinue transition");
    }

    if (m_windows_break != nullptr) {
        if (!m_windows_break->BindCurrentThread()) {
            LOG_CRITICAL(Core_ARM, "Failed to bind Windows NCE cross-thread break target");
        }
    }

    std::call_once(g_windows_veh_once, [] {
        g_windows_veh_handle = AddVectoredExceptionHandler(1, &WindowsNceVectoredExceptionHandler);
        if (g_windows_veh_handle == nullptr) {
            LOG_CRITICAL(Core_ARM, "Failed to install Windows NCE vectored exception handler");
        }
    });
}

void ArmNce::LockThreadParameters(void* raw_params) {
    auto* const params = static_cast<NativeExecutionParameters*>(raw_params);
    for (;;) {
        u32 expected = SpinLockUnlocked;
        if (params->lock.compare_exchange_weak(expected, SpinLockLocked,
                                               std::memory_order_acquire,
                                               std::memory_order_relaxed)) {
            return;
        }
        std::this_thread::yield();
    }
}

void ArmNce::UnlockThreadParameters(void* raw_params) {
    auto* const params = static_cast<NativeExecutionParameters*>(raw_params);
    params->lock.store(SpinLockUnlocked, std::memory_order_release);
}

void ArmNce::LockThread(Kernel::KThread* thread) {
    LockThreadParameters(&thread->GetNativeExecutionParameters());
}

void ArmNce::UnlockThread(Kernel::KThread* thread) {
    auto* const thread_params = &thread->GetNativeExecutionParameters();
    m_guest_ctx.tpidr_el0 = thread_params->tpidr_el0;
    m_guest_ctx.tpidrro_el0 = thread_params->tpidrro_el0;
    thread_params->native_context = nullptr;
    UnlockThreadParameters(thread_params);
}

HaltReason ArmNce::RunThread(Kernel::KThread* thread) {
    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));
    if (True(hr)) {
        return hr;
    }

    auto* const thread_params = &thread->GetNativeExecutionParameters();
    auto* const process = thread->GetOwnerProcess();

    m_running_thread = thread;
    m_guest_ctx.parent = this;
    thread_params->native_context = &m_guest_ctx;
    thread_params->tpidr_el0 = m_guest_ctx.tpidr_el0;
    thread_params->tpidrro_el0 = m_guest_ctx.tpidrro_el0;

    std::atomic_thread_fence(std::memory_order_release);
    thread_params->is_running = true;

    if (m_windows_x18_runner == nullptr) {
        m_windows_x18_runner = std::make_unique<NCE::WindowsX18FallbackRunner>(
            m_system, m_uses_wall_clock, process, m_core_index);
    }

    const auto& post_handlers = process->GetPostHandlers();
    std::optional<Common::HostMemory::PrivateMappingLease> private_stack_lease;

    for (;;) {
        // SignalInterrupt may defer delivery when another host-side NCE path already owns the
        // parameters lock. Honor that pending break before this lock-owning path can re-enter
        // native guest execution.
        const auto pending_reason =
            static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0, std::memory_order_acq_rel));
        if (True(pending_reason)) {
            hr = pending_reason;
            break;
        }

        NCE::CurrentNceContext::Install(thread_params);

        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,
                                          private_stack_lease)) {
            NCE::CurrentNceContext::Clear();
            hr = HaltReason::PrefetchAbort;
            break;
        }

        WindowsTebStackBounds teb_stack_bounds{};
        if (!InstallGuestTebStackBounds(m_guest_ctx, teb_stack_bounds)) {
            NCE::CurrentNceContext::Clear();
            hr = HaltReason::PrefetchAbort;
            break;
        }

        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(
                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));
        } else {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));
        }

        RestoreHostTebStackBounds(teb_stack_bounds);
        NCE::CurrentNceContext::Clear();

        const u64 unmatched_break_seq =
            m_windows_diag_unmatched_break_seq.exchange(0, std::memory_order_acq_rel);
        if (unmatched_break_seq != 0) {
            const u64 break_pc =
                m_windows_diag_unmatched_break_pc.load(std::memory_order_relaxed);
            const u64 break_sp =
                m_windows_diag_unmatched_break_sp.load(std::memory_order_relaxed);
            const u64 break_lr =
                m_windows_diag_unmatched_break_lr.load(std::memory_order_relaxed);
            const bool guest_mapped =
                m_windows_diag_unmatched_break_guest_mapped.load(std::memory_order_relaxed) != 0;

            MEMORY_BASIC_INFORMATION mbi{};
            const SIZE_T queried =
                VirtualQuery(reinterpret_cast<LPCVOID>(break_pc), &mbi, sizeof(mbi));

            HMODULE module{};
            char module_path[MAX_PATH]{};
            DWORD module_path_len = 0;
            if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                                       GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                   reinterpret_cast<LPCSTR>(break_pc), &module)) {
                module_path_len = GetModuleFileNameA(module, module_path, MAX_PATH);
            }

            const u64 exception_address =
                m_windows_diag_unmatched_break_exception_address.load(std::memory_order_relaxed);

            auto read_instruction = [](u64 address, u32& instruction) {
                SIZE_T bytes{};
                const BOOL ok =
                    ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(address),
                                      &instruction, sizeof(instruction), &bytes);
                return ok != FALSE && bytes == sizeof(instruction);
            };

            u32 instruction_at_pc{};
            u32 instruction_at_pc_minus4{};
            u32 instruction_at_exception{};
            const bool instruction_at_pc_ok =
                read_instruction(break_pc, instruction_at_pc);
            const bool instruction_at_pc_minus4_ok =
                break_pc >= sizeof(u32) &&
                read_instruction(break_pc - sizeof(u32), instruction_at_pc_minus4);
            const bool instruction_at_exception_ok =
                exception_address != 0 &&
                read_instruction(exception_address, instruction_at_exception);

            const u64 module_base = reinterpret_cast<u64>(module);
            const u64 allocation_base =
                queried != 0 ? reinterpret_cast<u64>(mbi.AllocationBase) : 0;
            const u64 module_rva =
                module_base != 0 && break_pc >= module_base ? break_pc - module_base : 0;

            LOG_ERROR(
                Core_ARM,
                "NCE_D2_UNMATCHED_BREAKPOINT seq={} pc={:#018x} sp={:#018x} lr={:#018x} "
                "guest_mapped={} exception_address={:#018x} module={} module_base={:#018x} "
                "rva={:#x} instruction_pc={:#010x} instruction_pc_ok={} "
                "instruction_pc_minus4={:#010x} instruction_pc_minus4_ok={} "
                "instruction_exception={:#010x} instruction_exception_ok={} "
                "sym_enter_guest_context={:#018x} sym_guest_stack_bridge={:#018x} "
                "sym_host_stack_bridge={:#018x} sym_v74_host_stack_bridge={:#018x} "
                "allocation_base={:#018x} protect={:#x} type={:#x}",
                unmatched_break_seq, break_pc, break_sp, break_lr, guest_mapped,
                exception_address, module_path_len != 0 ? module_path : "<unknown>",
                module_base, module_rva, instruction_at_pc, instruction_at_pc_ok,
                instruction_at_pc_minus4, instruction_at_pc_minus4_ok,
                instruction_at_exception, instruction_at_exception_ok,
                reinterpret_cast<u64>(&WindowsNceEnterGuestContext),
                reinterpret_cast<u64>(&WindowsNceGuestStackBridge),
                reinterpret_cast<u64>(&WindowsNceHostStackBridge),
                reinterpret_cast<u64>(&WindowsNceV74HostStackBridge),
                allocation_base, queried != 0 ? static_cast<u64>(mbi.Protect) : 0,
                queried != 0 ? static_cast<u64>(mbi.Type) : 0);
            hr = HaltReason::PrefetchAbort;
            break;
        }

        if (m_windows_pending_nce_fault) {
            static thread_local bool v74_return_logged = false;
            if (!v74_return_logged) {
                LOG_INFO(Core_ARM,
                         "NCE_V74_AV_PROVENANCE_RETURNED pc={:#018x} sp={:#018x}",
                         m_guest_ctx.pc, m_guest_ctx.sp);
                v74_return_logged = true;
            }

            const u64 pending_fault_address = m_windows_pending_nce_fault_address;
            const u64 pending_fault_page = m_windows_pending_nce_fault_page;
            m_windows_pending_nce_fault = false;
            m_windows_pending_nce_fault_address = 0;
            m_windows_pending_nce_fault_page = 0;

            if (process->GetMemory().InvalidateNCE(Common::ProcessAddress{pending_fault_page},
                                                   Memory::YUZU_PAGESIZE)) {
                continue;
            }

            if (m_guest_ctx.pc != pending_fault_address) {
                m_guest_ctx.pc += sizeof(u32);
                continue;
            }

            hr = HaltReason::PrefetchAbort;
            break;
        }

        // While the native guest stack is temporarily MEM_PRIVATE, Dynarmic fallback still
        // observes Core::Memory's section-backed storage. Synchronize the leased stack at this
        // engine boundary so both execution engines observe one coherent guest state.
        if (private_stack_lease.has_value() && !private_stack_lease->SyncToBacking()) {
            LOG_ERROR(Core_ARM, "V16 failed to synchronize private NCE stack to backing");
            hr = HaltReason::PrefetchAbort;
            break;
        }

        const auto fallback = m_windows_x18_runner->Dispatch(
            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);

        if (fallback.handled && private_stack_lease.has_value() &&
            !private_stack_lease->SyncFromBacking()) {
            LOG_ERROR(Core_ARM, "V16 failed to synchronize fallback stack writes to private view");
            hr = HaltReason::PrefetchAbort;
            break;
        }

        if (fallback.handled && private_stack_lease.has_value()) {
            static thread_local bool v16_sync_logged = false;
            if (!v16_sync_logged) {
                LOG_INFO(Core_ARM,
                         "NCE_V16_FALLBACK_STACK_SYNC pc={:#018x} sp={:#018x}",
                         m_guest_ctx.pc, m_guest_ctx.sp);
                v16_sync_logged = true;
            }
        }

        if (!fallback.handled) {
            break;
        }

        if (!fallback.metadata_found || !fallback.step.completed) {
            hr = fallback.step.halt_reason;
            if (!True(hr)) {
                hr = HaltReason::PrefetchAbort;
            }
            break;
        }

        if (True(fallback.step.halt_reason)) {
            hr = fallback.step.halt_reason;
            break;
        }

        // A normal one-instruction x18 fallback updated GuestContext::pc. Re-enter the native NCE
        // path using the same post-handler/arbitrary-PC selection contract as ordinary RunThread.
    }

    // The private replacement belongs to the complete RunThread epoch. Internal NCE fault/retry
    // iterations reuse it; restore the section-backed mapping exactly once when the epoch exits.
    if (private_stack_lease.has_value() && !private_stack_lease->Restore()) {
        LOG_ERROR(Core_ARM, "Failed to restore Windows NCE private stack lease");
        hr = HaltReason::PrefetchAbort;
    }

    std::atomic_thread_fence(std::memory_order_acquire);
    const u64 final_tpidr_el0 = thread_params->tpidr_el0;

    thread_params->is_running = false;
    thread_params->native_context = nullptr;
    m_running_thread = nullptr;
    m_guest_ctx.tpidr_el0 = final_tpidr_el0;

    return hr;
}

HaltReason ArmNce::StepThread(Kernel::KThread* thread) {
    (void)thread;
    return HaltReason::StepThread;
}

u32 ArmNce::GetSvcNumber() const {
    return m_guest_ctx.svc;
}

void ArmNce::GetSvcArguments(std::span<uint64_t, 8> args) const {
    for (size_t i = 0; i < args.size(); ++i) {
        args[i] = m_guest_ctx.cpu_registers[i];
    }
}

void ArmNce::SetSvcArguments(std::span<const uint64_t, 8> args) {
    for (size_t i = 0; i < args.size(); ++i) {
        m_guest_ctx.cpu_registers[i] = args[i];
    }
}

void ArmNce::SetTpidrroEl0(u64 value) {
    m_guest_ctx.tpidrro_el0 = value;
}

void ArmNce::GetContext(Kernel::Svc::ThreadContext& ctx) const {
    for (size_t i = 0; i < 29; ++i) {
        ctx.r[i] = m_guest_ctx.cpu_registers[i];
    }
    ctx.fp = m_guest_ctx.cpu_registers[29];
    ctx.lr = m_guest_ctx.cpu_registers[30];
    ctx.sp = m_guest_ctx.sp;
    ctx.pc = m_guest_ctx.pc;
    ctx.pstate = m_guest_ctx.pstate;
    ctx.v = m_guest_ctx.vector_registers;
    ctx.fpcr = m_guest_ctx.fpcr;
    ctx.fpsr = m_guest_ctx.fpsr;
    ctx.tpidr = m_guest_ctx.tpidr_el0;
}

void ArmNce::SetContext(const Kernel::Svc::ThreadContext& ctx) {
    for (size_t i = 0; i < 29; ++i) {
        m_guest_ctx.cpu_registers[i] = ctx.r[i];
    }
    m_guest_ctx.cpu_registers[29] = ctx.fp;
    m_guest_ctx.cpu_registers[30] = ctx.lr;
    m_guest_ctx.sp = ctx.sp;
    m_guest_ctx.pc = ctx.pc;
    m_guest_ctx.pstate = ctx.pstate;
    m_guest_ctx.nzcv = ctx.pstate & 0xF0000000U;
    m_guest_ctx.vector_registers = ctx.v;
    m_guest_ctx.fpcr = ctx.fpcr;
    m_guest_ctx.fpsr = ctx.fpsr;
    m_guest_ctx.tpidr_el0 = ctx.tpidr;
}

void ArmNce::SignalInterrupt(Kernel::KThread* thread) {
    m_guest_ctx.esr_el1.fetch_or(static_cast<u64>(HaltReason::BreakLoop),
                                 std::memory_order_acq_rel);

    auto* const params = &thread->GetNativeExecutionParameters();

    // Windows can request an interrupt from a different Boost.Context fiber on the same core
    // thread. If the NCE parameters are already locked, blocking here can deadlock against an
    // inactive lock-owning fiber. Leave BreakLoop pending and let that owner observe it at the
    // RunThread guest re-entry seam instead.
    u32 expected = SpinLockUnlocked;
    if (!params->lock.compare_exchange_strong(expected, SpinLockLocked,
                                              std::memory_order_acquire,
                                              std::memory_order_relaxed)) {
        return;
    }
    std::atomic_thread_fence(std::memory_order_acquire);

    if (!params->is_running) {
        UnlockThreadParameters(params);
        return;
    }

    if (m_windows_break == nullptr || !m_windows_break->IsBound()) {
        UnlockThreadParameters(params);
        return;
    }

    // The entry lock is released immediately before guest ownership. A concurrent interrupt can
    // therefore observe the tiny host-stack RtlRestoreContext window. Resume/retry that window
    // while retaining the scheduler-owned parameter lock; only a guest-stack context is saved and
    // redirected to the already-captured host continuation.
    for (;;) {
        BreakTransformState state{.nce = this};
        const bool delivery_ok =
            m_windows_break->SuspendTransformResume(&WindowsBreakTransform, &state);
        if (!delivery_ok) {
            UnlockThreadParameters(params);
            return;
        }
        if (state.transformed) {
            // The target returns through RunThread and PhysicalCore::ExitContext owns the matching
            // UnlockThread call, exactly as on the existing Linux NCE break path.
            return;
        }
        if (state.patch_window) {
            // Unlike the host-stack RtlRestoreContext window, generated patch code may itself need
            // to acquire NativeExecutionParameters::lock (notably the SVC lock prelude). Retaining
            // the sender-owned lock here can deadlock the target. Resume unchanged, release the
            // lock long enough for the generated helper to retire, then reacquire and retry.
            UnlockThreadParameters(params);
            std::this_thread::yield();
            LockThreadParameters(params);
            std::atomic_thread_fence(std::memory_order_acquire);
            if (!params->is_running) {
                UnlockThreadParameters(params);
                return;
            }
            continue;
        }
        if (!state.host_window) {
            UnlockThreadParameters(params);
            return;
        }

        // The captured target is executing on the host stack. PhysicalCore::Interrupt() owns
        // PhysicalCore::m_guard while calling us, so retaining the parameter lock and retrying
        // forever can deadlock a target that has already left RunThread and is waiting for that
        // same core guard in PhysicalCore::ExitContext(). Release ownership long enough for the
        // target to retire the host window, then perform a single non-blocking reacquire. If the
        // target has finished its RunThread epoch, return so Interrupt() can release m_guard.
        UnlockThreadParameters(params);
        std::this_thread::yield();

        expected = SpinLockUnlocked;
        if (!params->lock.compare_exchange_strong(expected, SpinLockLocked,
                                                  std::memory_order_acquire,
                                                  std::memory_order_relaxed)) {
            return;
        }
        std::atomic_thread_fence(std::memory_order_acquire);
        if (!params->is_running) {
            UnlockThreadParameters(params);
            return;
        }
    }
}

void ArmNce::ClearInstructionCache() {
    FlushInstructionCache(GetCurrentProcess(), nullptr, 0);
}

void ArmNce::InvalidateCacheRange(u64 addr, std::size_t size) {
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<const void*>(addr), size);
}

} // namespace Core
