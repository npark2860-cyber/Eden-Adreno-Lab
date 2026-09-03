// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_nce_transition.h"

#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_exception_context.h"

namespace Core::NCE {

bool WindowsNceTransition::Initialize() noexcept {
    if (m_nt_continue != nullptr) {
        return true;
    }

    const HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    if (ntdll == nullptr) {
        return false;
    }

    m_nt_continue = reinterpret_cast<NtContinueFn>(GetProcAddress(ntdll, "NtContinue"));
    return m_nt_continue != nullptr;
}

#if defined(_MSC_VER)
__declspec(noinline)
#endif
bool WindowsNceTransition::CaptureHostContext() noexcept {
    m_resume_pending.store(false, std::memory_order_relaxed);
    RtlCaptureContext(reinterpret_cast<PCONTEXT>(&m_host_context));
    return m_resume_pending.exchange(false, std::memory_order_acquire);
}

void WindowsNceTransition::PrepareGuestContext(const GuestContext& guest,
                                               ARM64_NT_CONTEXT& context) const noexcept {
    context = m_host_context;
    context.ContextFlags =
        CONTEXT_ARM64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT;
    WindowsExceptionContext::LoadGuestState(guest, context);
}

void WindowsNceTransition::RedirectToHost(ARM64_NT_CONTEXT& interrupted, GuestContext& guest,
                                          bool save_guest_state) noexcept {
    if (save_guest_state) {
        WindowsExceptionContext::SaveGuestState(guest, interrupted);
    }

    m_resume_pending.store(true, std::memory_order_release);
    interrupted = m_host_context;
    interrupted.ContextFlags =
        CONTEXT_ARM64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT;
}

LONG WindowsNceTransition::ContinueGuest(ARM64_NT_CONTEXT& guest_context) const noexcept {
    if (m_nt_continue == nullptr) {
        return static_cast<LONG>(0xC000000DL); // STATUS_INVALID_PARAMETER
    }
    return m_nt_continue(reinterpret_cast<PCONTEXT>(&guest_context), FALSE);
}

LONG WindowsNceTransition::ContinueHost() noexcept {
    if (m_nt_continue == nullptr) {
        return static_cast<LONG>(0xC000000DL); // STATUS_INVALID_PARAMETER
    }

    m_resume_pending.store(true, std::memory_order_release);
    return m_nt_continue(reinterpret_cast<PCONTEXT>(&m_host_context), FALSE);
}

extern "C"
#if defined(_MSC_VER)
__declspec(noinline)
#endif
void* GetCurrentNceContextForGeneratedCode() noexcept {
    return CurrentNceContext::Get();
}

} // namespace Core::NCE
