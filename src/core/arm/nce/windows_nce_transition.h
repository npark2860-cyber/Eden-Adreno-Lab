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

// Fixed Windows ARM64 entry. The assembly function saves the Windows ABI nonvolatile host state,
// restores guest architectural state except physical x18, and tail-enters entry_trampoline.
// entry_trampoline owns the final restoration of guest x17/x30 and branches to GuestContext::pc.
extern "C" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,
                                                const void* entry_trampoline) noexcept;

class WindowsNceTransition {
public:
    // Convert an externally suspended target back to the saved host ABI continuation. If the
    // interrupted PC/SP is known to be native guest execution, save that guest state first.
    // return_value becomes the x0 result of WindowsNceEnterGuest.
    static void RedirectToHost(ARM64_NT_CONTEXT& interrupted, GuestContext& guest,
                               bool save_guest_state, std::uint64_t return_value) noexcept;
};

// Stable C-linkage metadata locator for generated Windows NCE helpers. Generated code must call
// this fixed getter rather than embedding compiler/TEB TLS offsets.
extern "C" void* GetCurrentNceContextForGeneratedCode() noexcept;

} // namespace Core::NCE
