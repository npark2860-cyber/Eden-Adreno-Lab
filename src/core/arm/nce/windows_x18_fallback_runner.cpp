// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_x18_fallback_runner.h"

#include <limits>

#include "core/arm/dynarmic/arm_dynarmic_64.h"
#include "core/arm/dynarmic/dynarmic_exclusive_monitor.h"
#include "core/arm/nce/arm_nce.h"
#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/windows_x18_fallback_trap.h"
#include "core/core.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"

namespace Core::NCE {

WindowsX18FallbackRunner::WindowsX18FallbackRunner(System& system, bool uses_wall_clock,
                                                   Kernel::KProcess* process,
                                                   std::size_t core_index)
    : m_exclusive_monitor{std::make_unique<DynarmicExclusiveMonitor>(
          process->GetMemory(), Core::Hardware::NUM_CPU_CORES)},
      m_backend{std::make_unique<ArmDynarmic64>(system, uses_wall_clock, process,
                                                *m_exclusive_monitor, core_index, true)} {}

WindowsX18FallbackRunner::~WindowsX18FallbackRunner() = default;

WindowsX18FallbackDispatchResult WindowsX18FallbackRunner::Dispatch(
    u64 transition_result, Kernel::KThread* thread, GuestContext& guest,
    const X18FallbackMetadata& metadata, u64 private_stack_base,
    u64 private_stack_size) {
    WindowsX18FallbackDispatchResult result{};

    if (transition_result != WindowsX18FallbackTrap::ReturnMarker) {
        return result;
    }

    result.handled = true;
    const auto instruction = WindowsX18FallbackTrap::FindOriginalInstruction(guest.pc, metadata);
    if (!instruction) {
        return result;
    }

    result.metadata_found = true;

    if (private_stack_base != 0 && private_stack_size != 0) {
        m_backend->SetPrivateMemoryView(private_stack_base, private_stack_size);
    } else {
        m_backend->ClearPrivateMemoryView();
    }

    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);
    m_backend->ClearPrivateMemoryView();
    return result;
}

void WindowsX18FallbackRunner::SetDirectPrivateStackView(u64 base, u64 size) noexcept {
    if (base == 0 || size == 0 || base > std::numeric_limits<u64>::max() - size) {
        ClearDirectPrivateStackView();
        return;
    }
    m_direct_private_stack_base = base;
    m_direct_private_stack_size = size;
}

void WindowsX18FallbackRunner::ClearDirectPrivateStackView() noexcept {
    m_direct_private_stack_base = 0;
    m_direct_private_stack_size = 0;
}

X18FallbackStepResult WindowsX18FallbackRunner::ExecuteDirect(
    Kernel::KThread* thread, GuestContext& guest, u32 instruction) {
    if (m_direct_private_stack_base != 0 && m_direct_private_stack_size != 0) {
        m_backend->SetPrivateMemoryView(m_direct_private_stack_base,
                                        m_direct_private_stack_size);
    } else {
        m_backend->ClearPrivateMemoryView();
    }

    const auto step = X18Fallback::Step(*m_backend, thread, guest, instruction);
    m_backend->ClearPrivateMemoryView();
    return step;
}

extern "C" u64 WindowsNceExecuteDirectX18(GuestContext* guest, u32 instruction) noexcept {
    if (guest == nullptr || guest->parent == nullptr) {
        return static_cast<u64>(HaltReason::PrefetchAbort);
    }

    auto* const nce = guest->parent;
    auto* const thread = nce->m_running_thread;
    auto* const runner = nce->m_windows_x18_runner.get();
    if (thread == nullptr || runner == nullptr) {
        return static_cast<u64>(HaltReason::PrefetchAbort);
    }

    const u64 pending_before = guest->esr_el1.exchange(0, std::memory_order_acq_rel);
    if (pending_before != 0) {
        return pending_before;
    }

    const auto step = runner->ExecuteDirect(thread, *guest, instruction);

    const u64 pending_after = guest->esr_el1.exchange(0, std::memory_order_acq_rel);
    if (pending_after != 0) {
        return pending_after;
    }

    const u64 halt_reason = static_cast<u64>(step.halt_reason);
    if (!step.completed && halt_reason == 0) {
        return static_cast<u64>(HaltReason::PrefetchAbort);
    }
    return halt_reason;
}

} // namespace Core::NCE
