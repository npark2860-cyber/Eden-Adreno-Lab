// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_x18_fallback_trap.h"

#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/windows_nce_transition.h"

namespace Core::NCE {

std::optional<u32> WindowsX18FallbackTrap::FindOriginalInstruction(
    u64 pc, const X18FallbackSiteMap& sites) noexcept {
    const auto it = sites.find(pc);
    if (it == sites.end()) {
        return std::nullopt;
    }
    return it->second;
}

bool WindowsX18FallbackTrap::TryRedirect(PEXCEPTION_POINTERS exception, GuestContext& guest,
                                         const X18FallbackSiteMap& sites) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr ||
        exception->ExceptionRecord->ExceptionCode != EXCEPTION_BREAKPOINT) {
        return false;
    }

    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);
    if (!FindOriginalInstruction(context.Pc, sites).has_value()) {
        return false;
    }

    // Windows captured the full architectural context before this helper runs. RedirectToHost
    // saves all Windows-representable guest state while deliberately leaving physical x18 alone;
    // guest architectural x18 remains the virtual value already owned by GuestContext.
    WindowsNceTransition::RedirectToHost(context, guest, true, ReturnMarker);
    return true;
}

} // namespace Core::NCE
