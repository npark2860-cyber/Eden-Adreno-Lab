// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#ifdef _WIN32

#include <cstdint>
#include <windows.h>

namespace Core::NCE {

class WindowsCrossThreadBreak {
public:
    using ContextTransform = bool (*)(ARM64_NT_CONTEXT& context, void* opaque) noexcept;

    WindowsCrossThreadBreak() = default;

    ~WindowsCrossThreadBreak() {
        Reset();
    }

    WindowsCrossThreadBreak(const WindowsCrossThreadBreak&) = delete;
    WindowsCrossThreadBreak& operator=(const WindowsCrossThreadBreak&) = delete;

    WindowsCrossThreadBreak(WindowsCrossThreadBreak&& other) noexcept
        : m_thread{other.m_thread}, m_host_stack_low{other.m_host_stack_low},
          m_host_stack_high{other.m_host_stack_high} {
        other.m_thread = nullptr;
        other.m_host_stack_low = 0;
        other.m_host_stack_high = 0;
    }

    WindowsCrossThreadBreak& operator=(WindowsCrossThreadBreak&& other) noexcept {
        if (this != &other) {
            Reset();
            m_thread = other.m_thread;
            m_host_stack_low = other.m_host_stack_low;
            m_host_stack_high = other.m_host_stack_high;
            other.m_thread = nullptr;
            other.m_host_stack_low = 0;
            other.m_host_stack_high = 0;
        }
        return *this;
    }

    // Must be called by the target NCE host thread before another thread can request a break.
    [[nodiscard]] bool BindCurrentThread() noexcept {
        Reset();

        HANDLE duplicate{};
        const HANDLE process = GetCurrentProcess();
        constexpr DWORD rights =
            THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_SET_CONTEXT;
        if (!DuplicateHandle(process, GetCurrentThread(), process, &duplicate, rights, FALSE, 0)) {
            return false;
        }

        const auto* const tib = reinterpret_cast<const NT_TIB*>(NtCurrentTeb());
        m_host_stack_low = reinterpret_cast<std::uintptr_t>(tib->StackLimit);
        m_host_stack_high = reinterpret_cast<std::uintptr_t>(tib->StackBase);
        m_thread = duplicate;
        return true;
    }

    // Suspend the target without executing any callback on its user stack, capture its native ARM64
    // state, allow the caller to classify/mutate that state, and resume it. Returning false from the
    // transform leaves the captured state unchanged and merely resumes the target. This is only the
    // Windows delivery primitive; deciding whether the captured PC is guest code or an IMP-005
    // transition window belongs to the transition owner.
    [[nodiscard]] bool SuspendTransformResume(ContextTransform transform,
                                              void* opaque = nullptr) const noexcept {
        if (m_thread == nullptr || transform == nullptr) {
            return false;
        }

        const DWORD previous_suspend_count = SuspendThread(m_thread);
        if (previous_suspend_count == static_cast<DWORD>(-1)) {
            return false;
        }

        ARM64_NT_CONTEXT context{};
        context.ContextFlags =
            CONTEXT_ARM64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT;

        bool success =
            GetThreadContext(m_thread, reinterpret_cast<PCONTEXT>(&context)) != FALSE;
        if (success && transform(context, opaque)) {
            success = SetThreadContext(m_thread, reinterpret_cast<PCONTEXT>(&context)) != FALSE;
        }

        const DWORD resume_count = ResumeThread(m_thread);
        if (resume_count == static_cast<DWORD>(-1)) {
            return false;
        }

        return success;
    }

    [[nodiscard]] bool IsHostStackPointer(DWORD64 sp) const noexcept {
        const auto value = static_cast<std::uintptr_t>(sp);
        return m_host_stack_low != 0 && value >= m_host_stack_low && value < m_host_stack_high;
    }

    [[nodiscard]] bool IsBound() const noexcept {
        return m_thread != nullptr;
    }

private:
    void Reset() noexcept {
        if (m_thread != nullptr) {
            CloseHandle(m_thread);
            m_thread = nullptr;
        }
        m_host_stack_low = 0;
        m_host_stack_high = 0;
    }

    HANDLE m_thread{};
    std::uintptr_t m_host_stack_low{};
    std::uintptr_t m_host_stack_high{};
};

} // namespace Core::NCE

#endif // _WIN32
