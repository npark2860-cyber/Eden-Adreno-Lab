// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#if !defined(_WIN32)
#error windows_x18_fallback_runner.h is only available on Windows.
#endif

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>

#include "common/common_types.h"
#include "core/arm/nce/x18_fallback.h"
#include "core/arm/nce/x18_site_patcher.h"

namespace Kernel {
class KProcess;
class KThread;
}

namespace Core {

class ArmDynarmic64;
class DynarmicExclusiveMonitor;
class System;
struct GuestContext;

namespace NCE {

struct WindowsX18FallbackDispatchResult {
    bool handled{};
    bool metadata_found{};
    X18FallbackStepResult step{};
};

// Windows-only owner for the selective Dynarmic backend used by IMP-006. The private exclusive
// monitor exists only because ArmDynarmic64 requires one; IMP-006 never routes exclusive/LSE
// instructions here, so native NCE reservation state is not shared or transferred.
//
// The integrated ArmNce loop remains an IMP-008 concern. This class owns only the ordinary
// guest-x18 fallback seam and can later be embedded by the Windows ArmNce implementation.
class WindowsX18FallbackRunner {
public:
    WindowsX18FallbackRunner(System& system, bool uses_wall_clock, Kernel::KProcess* process,
                             std::size_t core_index);
    ~WindowsX18FallbackRunner();

    WindowsX18FallbackRunner(const WindowsX18FallbackRunner&) = delete;
    WindowsX18FallbackRunner& operator=(const WindowsX18FallbackRunner&) = delete;

    [[nodiscard]] WindowsX18FallbackDispatchResult Dispatch(
        u64 transition_result, Kernel::KThread* thread, GuestContext& guest,
        const X18FallbackMetadata& metadata);

private:
    std::unique_ptr<DynarmicExclusiveMonitor> m_exclusive_monitor;
    std::unique_ptr<ArmDynarmic64> m_backend;
    std::size_t m_core_index{};

    // V56 diagnostic only: detect whether the selective Dynarmic fallback backend is entered again
    // before a previous one-instruction Step has retired. The mutex protects only this metadata and
    // is never held across Dynarmic execution, so it does not serialize or hide a real re-entry.
    std::mutex m_v56_diag_mutex;
    u32 m_v56_active_dispatches{};
    u32 m_v56_owner_host_tid{};
    std::uintptr_t m_v56_owner_kthread{};
    u64 m_v56_owner_pc{};
    u64 m_v56_owner_sp{};
};

} // namespace NCE
} // namespace Core
