// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#if !defined(_WIN32)
#error arm_nce_windows.cpp is only available on Windows.
#endif

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <atomic>
#include <memory>
#include <mutex>
#include <thread>

#include "core/arm/nce/arm_nce.h"
#include "core/arm/nce/arm_nce_asm_definitions.h"
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_cross_thread_break.h"
#include "core/arm/nce/windows_exception_context.h"
#include "core/arm/nce/windows_nce_transition.h"
#include "core/arm/nce/windows_x18_fallback_runner.h"
#include "core/arm/nce/windows_x18_fallback_trap.h"
#include "core/core.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"
#include "core/memory.h"

namespace Core {

namespace {

using NativeExecutionParameters = Kernel::KThread::NativeExecutionParameters;

static_assert(offsetof(NativeExecutionParameters, native_context) == TpidrEl0NativeContext);
static_assert(offsetof(NativeExecutionParameters, lock) == TpidrEl0Lock);
static_assert(offsetof(NativeExecutionParameters, magic) == TpidrEl0TlsMagic);

std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

struct BreakTransformState {
    ArmNce* nce{};
    bool transformed{};
    bool host_window{};
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
        if (NCE::WindowsX18FallbackTrap::TryRedirect(exception, *guest,
                                                     process->GetPostHandlers())) {
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        params->lock.store(SpinLockUnlocked, std::memory_order_release);
        return EXCEPTION_CONTINUE_SEARCH;
    }

    if (NCE::WindowsExceptionContext::IsAccessViolation(*exception->ExceptionRecord)) {
        const auto fault_address = reinterpret_cast<u64>(
            NCE::WindowsExceptionContext::GetFaultAddress(*exception->ExceptionRecord));
        const auto page_address = Common::ProcessAddress{fault_address & ~Memory::YUZU_PAGEMASK};

        // Preserve Eden's existing NCE invalidation policy for guest data/execute faults.
        if (process->GetMemory().InvalidateNCE(page_address, Memory::YUZU_PAGESIZE)) {
            return EXCEPTION_CONTINUE_EXECUTION;
        }

        // Match the existing Linux NCE failed-fault policy. Data aborts skip the faulting
        // instruction; execute/prefetch aborts return to PhysicalCore for debugger/suspend policy.
        if (context.Pc != fault_address) {
            context.Pc += sizeof(u32);
            return EXCEPTION_CONTINUE_EXECUTION;
        }

        guest->esr_el1.fetch_or(static_cast<u64>(HaltReason::PrefetchAbort),
                                std::memory_order_acq_rel);
        params->lock.store(SpinLockLocked, std::memory_order_release);
        const auto reason = guest->esr_el1.exchange(0, std::memory_order_acq_rel);
        NCE::WindowsNceTransition::RedirectToHost(context, *guest, true, reason);
        return EXCEPTION_CONTINUE_EXECUTION;
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
    if (m_windows_break != nullptr && !m_windows_break->IsBound()) {
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

    for (;;) {
        NCE::CurrentNceContext::Install(thread_params);
        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(
                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));
        } else {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));
        }
        NCE::CurrentNceContext::Clear();

        const auto fallback = m_windows_x18_runner->Dispatch(
            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);
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
    m_guest_ctx.vector_registers = ctx.v;
    m_guest_ctx.fpcr = ctx.fpcr;
    m_guest_ctx.fpsr = ctx.fpsr;
    m_guest_ctx.tpidr_el0 = ctx.tpidr;
}

void ArmNce::SignalInterrupt(Kernel::KThread* thread) {
    m_guest_ctx.esr_el1.fetch_or(static_cast<u64>(HaltReason::BreakLoop),
                                 std::memory_order_acq_rel);

    auto* const params = &thread->GetNativeExecutionParameters();
    LockThreadParameters(params);
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
        if (!state.host_window) {
            UnlockThreadParameters(params);
            return;
        }
        std::this_thread::yield();
    }
}

void ArmNce::ClearInstructionCache() {
    FlushInstructionCache(GetCurrentProcess(), nullptr, 0);
}

void ArmNce::InvalidateCacheRange(u64 addr, std::size_t size) {
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<const void*>(addr), size);
}

} // namespace Core
