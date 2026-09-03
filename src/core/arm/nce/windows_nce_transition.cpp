// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_nce_transition.h"

#include <cstring>

#include "core/arm/nce/arm_nce_asm_definitions.h"
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_exception_context.h"

namespace Core::NCE {

static_assert(offsetof(GuestContext, host_ctx) == GuestContextHostContext);
static_assert(offsetof(HostContext, host_saved_regs) == HostContextRegs);
static_assert(offsetof(HostContext, host_saved_vregs) == HostContextVregs);
static_assert(offsetof(HostContext, host_sp) == HostContextSpTpidrEl0);

bool WindowsNceTransition::IsEntryBreakpoint(const EXCEPTION_POINTERS& exception) noexcept {
    if (exception.ExceptionRecord == nullptr || exception.ContextRecord == nullptr) {
        return false;
    }
    if (exception.ExceptionRecord->ExceptionCode != EXCEPTION_BREAKPOINT) {
        return false;
    }
    return exception.ExceptionRecord->ExceptionAddress ==
           reinterpret_cast<void*>(&WindowsNceEntryBreakpoint);
}

void WindowsNceTransition::PrepareGuestEntry(const GuestContext& guest,
                                             ARM64_NT_CONTEXT& context) noexcept {
    context.ContextFlags =
        CONTEXT_ARM64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT;
    WindowsExceptionContext::LoadGuestState(guest, context);
}

void WindowsNceTransition::RedirectToHost(ARM64_NT_CONTEXT& interrupted, GuestContext& guest,
                                          bool save_guest_state,
                                          std::uint64_t return_value) noexcept {
    if (save_guest_state) {
        WindowsExceptionContext::SaveGuestState(guest, interrupted);
    }

    const HostContext& host = guest.host_ctx;

    for (std::size_t i = 0; i < host.host_saved_regs.size(); ++i) {
        interrupted.X[19 + i] = host.host_saved_regs[i];
    }
    std::memcpy(&interrupted.V[8], host.host_saved_vregs.data(),
                sizeof(host.host_saved_vregs));

    interrupted.Sp = host.host_sp;
    interrupted.Pc = host.host_saved_regs[11];
    interrupted.X0 = return_value;
    interrupted.ContextFlags =
        CONTEXT_ARM64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT;
}

extern "C"
#if defined(_MSC_VER)
__declspec(noinline)
#endif
void* GetCurrentNceContextForGeneratedCode() noexcept {
    return CurrentNceContext::Get();
}

} // namespace Core::NCE
