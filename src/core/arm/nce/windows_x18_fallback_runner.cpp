// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_x18_fallback_runner.h"

#include <windows.h>

#include "common/assert.h"
#include "common/logging.h"

#include "core/arm/dynarmic/arm_dynarmic_64.h"
#include "core/arm/dynarmic/dynarmic_exclusive_monitor.h"
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
                                                *m_exclusive_monitor, core_index)},
      m_core_index{core_index} {}

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

    const u32 current_tid = static_cast<u32>(GetCurrentThreadId());
    u32 expected_owner_tid = 0;
    const bool owns_backend = m_v59_owner_host_tid.compare_exchange_strong(
        expected_owner_tid, current_tid, std::memory_order_acq_rel, std::memory_order_acquire);

    if (!owns_backend) {
        LOG_CRITICAL(
            Core_ARM,
            "NCE_V59_X18_OVERLAP runner=0x{:016X} backend=0x{:016X} core={} "
            "current_tid={} owner_tid={} current_kthread=0x{:016X} "
            "pc=0x{:016X} sp=0x{:016X} instruction=0x{:08X}",
            reinterpret_cast<std::uintptr_t>(this),
            reinterpret_cast<std::uintptr_t>(m_backend.get()), m_core_index, current_tid,
            expected_owner_tid, reinterpret_cast<std::uintptr_t>(thread), guest.pc, guest.sp,
            *instruction);
    }

    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);

    if (owns_backend) {
        u32 owner_tid = current_tid;
        const bool released = m_v59_owner_host_tid.compare_exchange_strong(
            owner_tid, 0, std::memory_order_release, std::memory_order_relaxed);
        ASSERT(released);
    }

    return result;
}

} // namespace Core::NCE
