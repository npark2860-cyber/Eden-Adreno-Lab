// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "core/hle/kernel/k_thread.h"

namespace Core::NCE {

class CurrentNceContext {
public:
    using Parameters = Kernel::KThread::NativeExecutionParameters;

    static void Install(Parameters* parameters) noexcept {
        current = parameters;
    }

    static Parameters* Get() noexcept {
        return current;
    }

    static void Clear() noexcept {
        current = nullptr;
    }

private:
    inline static thread_local Parameters* current{};
};

} // namespace Core::NCE
