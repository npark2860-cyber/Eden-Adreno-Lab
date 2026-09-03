// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#ifdef _WIN32

#include <windows.h>

namespace Core::NCE {

class WindowsCrossThreadBreak {
public:
    WindowsCrossThreadBreak() = default;

    ~WindowsCrossThreadBreak() {
        Reset();
    }

    WindowsCrossThreadBreak(const WindowsCrossThreadBreak&) = delete;
    WindowsCrossThreadBreak& operator=(const WindowsCrossThreadBreak&) = delete;

    WindowsCrossThreadBreak(WindowsCrossThreadBreak&& other) noexcept
        : m_thread{other.m_thread} {
        other.m_thread = nullptr;
    }

    WindowsCrossThreadBreak& operator=(WindowsCrossThreadBreak&& other) noexcept {
        if (this != &other) {
            Reset();
            m_thread = other.m_thread;
            other.m_thread = nullptr;
        }
        return *this;
    }

    // Must be called by the target NCE host thread before another thread can queue a break.
    [[nodiscard]] bool BindCurrentThread() noexcept {
        Reset();

        HANDLE duplicate{};
        const HANDLE process = GetCurrentProcess();
        if (!DuplicateHandle(process, GetCurrentThread(), process, &duplicate, THREAD_SET_CONTEXT,
                             FALSE, 0)) {
            return false;
        }

        m_thread = duplicate;
        return true;
    }

    // The supplied return target is an IMP-005-owned Windows ARM64 guest->host return stub.
    [[nodiscard]] bool QueueBreak(void* return_target) const noexcept {
        if (m_thread == nullptr || return_target == nullptr) {
            return false;
        }

        constexpr auto flags = static_cast<QUEUE_USER_APC_FLAGS>(
            static_cast<unsigned>(QUEUE_USER_APC_FLAGS_SPECIAL_USER_APC) |
            static_cast<unsigned>(QUEUE_USER_APC_CALLBACK_DATA_CONTEXT));

        return QueueUserAPC2(&BreakCallback, m_thread, reinterpret_cast<ULONG_PTR>(return_target),
                             flags) != FALSE;
    }

    [[nodiscard]] bool IsBound() const noexcept {
        return m_thread != nullptr;
    }

private:
    static VOID CALLBACK BreakCallback(ULONG_PTR raw_callback_data) noexcept {
        auto* const callback_data = reinterpret_cast<PAPC_CALLBACK_DATA>(raw_callback_data);
        if (callback_data == nullptr || callback_data->ContextRecord == nullptr ||
            callback_data->Parameter == 0) {
            return;
        }

        // Keep the asynchronous APC path deliberately minimal: only redirect the interrupted PC.
        // Guest-state saving, BreakLoop consumption and NativeExecutionParameters unlock belong to
        // the Windows transition stub implemented by IMP-005.
        callback_data->ContextRecord->Pc = static_cast<DWORD64>(callback_data->Parameter);
    }

    void Reset() noexcept {
        if (m_thread != nullptr) {
            CloseHandle(m_thread);
            m_thread = nullptr;
        }
    }

    HANDLE m_thread{};
};

} // namespace Core::NCE

#endif // _WIN32
