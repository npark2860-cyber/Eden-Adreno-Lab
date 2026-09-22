// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>

namespace Common::WindowsNcePostAudioProbe {

inline std::atomic<unsigned> g_stage{0};

inline void Arm() noexcept {
    g_stage.store(1, std::memory_order_release);
}

inline bool ObserveRunThread() noexcept {
    if (g_stage.load(std::memory_order_relaxed) != 1) {
        return false;
    }
    unsigned expected = 1;
    return g_stage.compare_exchange_strong(expected, 2, std::memory_order_acq_rel,
                                           std::memory_order_acquire);
}

inline bool ObserveEnterGuest() noexcept {
    if (g_stage.load(std::memory_order_relaxed) != 2) {
        return false;
    }
    unsigned expected = 2;
    return g_stage.compare_exchange_strong(expected, 3, std::memory_order_acq_rel,
                                           std::memory_order_acquire);
}

} // namespace Common::WindowsNcePostAudioProbe
