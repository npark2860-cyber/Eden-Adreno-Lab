// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#if !defined(_WIN32)
#error windows_x18_fallback_runner.h is only available on Windows.
#endif

#include <cstddef>
#include <memory>

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

// Windows-only owner for the selective Dynarmic backend used by IMP-006. The integrated ArmNce
// loop remains an IMP-008 concern; this class owns only the ordinary guest-x18 fallback seam.
class WindowsX18FallbackRunner {
public:
    WindowsX18FallbackRunner(System& system, bool uses_wall_clock, Kernel::KProcess* process,
                             DynarmicExclusiveMonitor& exclusive_monitor,
                             std::size_t core_index);
    ~WindowsX18FallbackRunner();

    WindowsX18FallbackRunner(const WindowsX18FallbackRunner&) = delete;
    WindowsX18FallbackRunner& operator=(const WindowsX18FallbackRunner&) = delete;

    [[nodiscard]] WindowsX18FallbackDispatchResult Dispatch(
        u64 transition_result, Kernel::KThread* thread, GuestContext& guest,
        const X18FallbackMetadata& metadata);

private:
    std::unique_ptr<ArmDynarmic64> m_backend;
};

} // namespace NCE
} // namespace Core
