// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_x18_fallback_runner.h"

#include "core/arm/dynarmic/arm_dynarmic_64.h"
#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/windows_x18_fallback_trap.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_thread.h"

namespace Core::NCE {

WindowsX18FallbackRunner::WindowsX18FallbackRunner(
    System& system, bool uses_wall_clock, Kernel::KProcess* process,
    DynarmicExclusiveMonitor& exclusive_monitor, std::size_t core_index)
    : m_backend{std::make_unique<ArmDynarmic64>(system, uses_wall_clock, process,
                                                exclusive_monitor, core_index)} {}

WindowsX18FallbackRunner::~WindowsX18FallbackRunner() = default;

WindowsX18FallbackDispatchResult WindowsX18FallbackRunner::Dispatch(
    u64 transition_result, Kernel::KThread* thread, GuestContext& guest,
    const X18FallbackMetadata& metadata) {
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
    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);
    return result;
}

} // namespace Core::NCE
