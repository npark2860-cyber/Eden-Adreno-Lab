// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_nce_transition.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "core/arm/nce/arm_nce_asm_definitions.h"
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_exception_context.h"

namespace Core::NCE {

namespace {
constexpr std::uint32_t NzcvMask = 0xF0000000U;

void TraceVirtualMapping(const char* name, std::uint64_t address) noexcept {
    MEMORY_BASIC_INFORMATION mbi{};
    const SIZE_T size = VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi));
    std::fprintf(stderr,
                 "IMP008B_E2_%s_ADDR=0x%llX QUERY=%llu BASE=%p ALLOC=%p STATE=0x%lX "
                 "PROTECT=0x%lX TYPE=0x%lX\n",
                 name, static_cast<unsigned long long>(address),
                 static_cast<unsigned long long>(size), mbi.BaseAddress, mbi.AllocationBase,
                 static_cast<unsigned long>(mbi.State), static_cast<unsigned long>(mbi.Protect),
                 static_cast<unsigned long>(mbi.Type));
    std::fflush(stderr);
}
} // namespace

static_assert(offsetof(GuestContext, cpu_registers) == 0x000);
static_assert(offsetof(GuestContext, sp) == GuestContextSp);
static_assert(offsetof(GuestContext, fpcr) == 0x108);
static_assert(offsetof(GuestContext, fpsr) == 0x10C);
static_assert(offsetof(GuestContext, vector_registers) == 0x110);
static_assert(offsetof(GuestContext, pstate) == 0x310);
static_assert(offsetof(GuestContext, host_ctx) == GuestContextHostContext);
static_assert(offsetof(HostContext, host_saved_regs) == HostContextRegs);
static_assert(offsetof(HostContext, host_saved_vregs) == HostContextVregs);
static_assert(offsetof(HostContext, host_sp) == HostContextSpTpidrEl0);

extern "C" [[noreturn]] void WindowsNceRestoreGuestContext(GuestContext* guest) noexcept {
    std::fputs("IMP008B_E2_RESTORE_ENTER=PASS\n", stderr);
    std::fflush(stderr);

    ARM64_NT_CONTEXT context{};
    RtlCaptureContext(reinterpret_cast<PCONTEXT>(&context));

    // Load guest state into the captured Windows context. WindowsExceptionContext deliberately
    // skips architectural x18, so context.X[18] remains the live Windows/TEB platform value.
    const auto platform_cpsr = context.Cpsr & ~NzcvMask;
    WindowsExceptionContext::LoadGuestState(*guest, context);

    // Native NCE owns guest NZCV only. Preserve the platform-owned non-NZCV PSTATE bits captured
    // from Windows rather than allowing guest state to alter them.
    context.Cpsr = platform_cpsr | (guest->pstate & NzcvMask);
    context.ContextFlags =
        CONTEXT_ARM64 | CONTEXT_CONTROL | CONTEXT_INTEGER | CONTEXT_FLOATING_POINT;

    // Match the existing Linux NCE ownership handoff: PhysicalCore enters RunThread with the
    // NativeExecutionParameters lock held, but native guest code owns an unlocked interval so SVC,
    // fault and cross-thread-break paths can acquire it. This is the last host-side state mutation
    // before RtlRestoreContext transfers control to guest SP/PC.
    auto* const parameters = CurrentNceContext::Get();
    if (parameters == nullptr || parameters->native_context != guest) {
        std::abort();
    }
    std::fputs("IMP008B_E2_RESTORE_CONTEXT_MATCH=PASS\n", stderr);
    std::fflush(stderr);

    parameters->lock.store(SpinLockUnlocked, std::memory_order_release);

    std::fprintf(stderr,
                 "IMP008B_E2_RESTORE_CONTEXT PC=0x%llX SP=0x%llX X18=0x%llX CPSR=0x%08lX "
                 "FLAGS=0x%08lX\n",
                 static_cast<unsigned long long>(context.Pc),
                 static_cast<unsigned long long>(context.Sp),
                 static_cast<unsigned long long>(context.X[18]),
                 static_cast<unsigned long>(context.Cpsr),
                 static_cast<unsigned long>(context.ContextFlags));
    std::fflush(stderr);
    TraceVirtualMapping("RESTORE_PC", context.Pc);
    TraceVirtualMapping("RESTORE_SP", context.Sp);

    std::fputs("IMP008B_E2_BEFORE_RTL_RESTORE=PASS\n", stderr);
    std::fflush(stderr);
    RtlRestoreContext(reinterpret_cast<PCONTEXT>(&context), nullptr);
    std::fputs("IMP008B_E2_RTL_RESTORE_RETURNED=PASS\n", stderr);
    std::fflush(stderr);
    std::abort();
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
