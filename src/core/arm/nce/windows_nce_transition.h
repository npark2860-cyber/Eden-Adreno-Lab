// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#if !defined(_WIN32)
#error windows_nce_transition.h is only available on Windows.
#endif

#include <cstdint>
#include <windows.h>

#include "core/arm/nce/guest_context.h"

namespace Core::NCE {

// Fixed Windows ARM64 entry gate. The assembly function saves the host ABI nonvolatile state and
// host SP into GuestContext::host_ctx, then executes the exported breakpoint while SP is still the
// Windows host stack. A VEH owner can atomically overlay the full guest-visible ARM64 CONTEXT and
// continue at GuestContext::pc without borrowing physical x18 or TPIDR_EL0.
extern "C" std::uint64_t WindowsNceEnterGuest(GuestContext* guest) noexcept;
extern "C" void WindowsNceEntryBreakpoint() noexcept;

class WindowsNceTransition {
public:
    [[nodiscard]] static bool IsEntryBreakpoint(const EXCEPTION_POINTERS& exception) noexcept;

    // Convert the host-stack breakpoint CONTEXT into guest state. WindowsExceptionContext excludes
    // physical x18, so the live Windows TEB register remains Windows-owned.
    static void PrepareGuestEntry(const GuestContext& guest, ARM64_NT_CONTEXT& context) noexcept;

    // Convert an externally suspended target back to the saved host ABI continuation. If the
    // interrupted PC/SP is known to be native guest execution, save that guest state first. For a
    // host-stack transition window pass save_guest_state=false so pre-entry GuestContext remains
    // authoritative. return_value becomes the x0 result of WindowsNceEnterGuest.
    static void RedirectToHost(ARM64_NT_CONTEXT& interrupted, GuestContext& guest,
                               bool save_guest_state, std::uint64_t return_value) noexcept;
};

// Stable C-linkage metadata locator for generated Windows NCE helpers. Generated code must call
// this fixed getter rather than embedding compiler/TEB TLS offsets.
extern "C" void* GetCurrentNceContextForGeneratedCode() noexcept;

} // namespace Core::NCE
