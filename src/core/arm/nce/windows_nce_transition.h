// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#if !defined(_WIN32)
#error windows_nce_transition.h is only available on Windows.
#endif

#include <atomic>
#include <cstdint>
#include <windows.h>

#include "core/arm/nce/guest_context.h"

namespace Core::NCE {

// Host-side Windows ARM64 transition state. The target host thread captures a resumable Windows
// CONTEXT before native guest entry. Guest entry itself uses NtContinue, while cross-thread breaks
// may replace an interrupted CONTEXT with this captured host continuation.
class WindowsNceTransition {
public:
    using NtContinueFn = LONG(NTAPI*)(PCONTEXT context, BOOLEAN test_alert);

    WindowsNceTransition() = default;

    [[nodiscard]] bool Initialize() noexcept;
    [[nodiscard]] bool IsInitialized() const noexcept {
        return m_nt_continue != nullptr;
    }

    // Returns false on the initial host pass. When a Windows break or synchronous generated helper
    // restores the captured host CONTEXT, execution resumes immediately after RtlCaptureContext and
    // this method returns true instead.
    [[nodiscard]] bool CaptureHostContext() noexcept;

    // Start from the captured host CONTEXT so Windows-owned state, especially physical x18/TEB, is
    // never populated from GuestContext. The Windows exception adapter then overlays guest-visible
    // architectural state, explicitly excluding x18.
    void PrepareGuestContext(const GuestContext& guest, ARM64_NT_CONTEXT& context) const noexcept;

    // Convert an externally suspended target back to the captured host continuation. If the target
    // was already executing native guest code, save that guest state first. If it was still in the
    // host-stack entry window, GuestContext already contains the authoritative pre-entry state and
    // must not be overwritten with host transition registers.
    void RedirectToHost(ARM64_NT_CONTEXT& interrupted, GuestContext& guest,
                        bool save_guest_state) noexcept;

    // Mark the captured continuation as a host resume and invoke NtContinue. Successful NtContinue
    // does not return to the caller; instead CaptureHostContext resumes and reports true.
    [[nodiscard]] LONG ContinueGuest(ARM64_NT_CONTEXT& guest_context) const noexcept;
    [[nodiscard]] LONG ContinueHost() noexcept;

    [[nodiscard]] DWORD64 HostStackPointer() const noexcept {
        return m_host_context.Sp;
    }

private:
    ARM64_NT_CONTEXT m_host_context{};
    std::atomic<bool> m_resume_pending{};
    NtContinueFn m_nt_continue{};
};

// Stable C-linkage metadata locator for generated Windows NCE helpers. The MSVC ARM64 lowering of
// this fixed getter is verified separately to be leaf and stackless; generated code must preserve
// the getter's observed volatile clobbers rather than embedding compiler TLS offsets itself.
extern "C" void* GetCurrentNceContextForGeneratedCode() noexcept;

} // namespace Core::NCE
