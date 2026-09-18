// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/windows_nce_transition.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>

#include "core/arm/nce/arm_nce.h"
#include "core/arm/nce/arm_nce_asm_definitions.h"
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_cross_thread_break.h"
#include "core/arm/nce/windows_exception_context.h"

namespace Core::NCE {

extern "C" void WindowsNceGuestStackBridge() noexcept;
extern "C" void WindowsNceHostStackBridge() noexcept;

namespace {
constexpr std::uint32_t NzcvMask = 0xF0000000U;

using NtContinueFn = LONG(NTAPI*)(PCONTEXT, BOOLEAN);
std::once_flag g_nt_continue_once;
NtContinueFn g_nt_continue{};

void ResolveNtContinue() noexcept {
    const HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    g_nt_continue =
        ntdll != nullptr ? reinterpret_cast<NtContinueFn>(GetProcAddress(ntdll, "NtContinue"))
                         : nullptr;
}

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

bool WindowsNceTransition::Initialize() noexcept {
    std::call_once(g_nt_continue_once, ResolveNtContinue);
    return g_nt_continue != nullptr;
}

[[noreturn]] void WindowsNceTransition::ContinueContext(ARM64_NT_CONTEXT& context) noexcept {
    const auto nt_continue = g_nt_continue;
    if (nt_continue == nullptr) {
        std::abort();
    }

    const LONG status = nt_continue(reinterpret_cast<PCONTEXT>(&context), FALSE);
    std::fprintf(stderr, "IMP008B_E2_NT_CONTINUE_RETURN=0x%08lX\n",
                 static_cast<unsigned long>(status));
    std::fflush(stderr);
    std::abort();
}

extern "C" [[noreturn]] void WindowsNceContinueGuestContext(
    ARM64_NT_CONTEXT* context) noexcept {
    if (context == nullptr) {
        std::abort();
    }
    WindowsNceTransition::ContinueContext(*context);
}

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
    // before the Windows context transition transfers control to guest SP/PC.
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

    // RtlRestoreContext converts a rejected NtContinue into an immediate fail-fast. Call the
    // underlying transition directly so the arbitrary-PC guest restore and exception continuation
    // share the same Windows context-resume primitive.
    std::fputs("IMP008B_E2_BEFORE_NT_CONTINUE=PASS\n", stderr);
    std::fflush(stderr);

    MEMORY_BASIC_INFORMATION stack_mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(guest->sp - 1), &stack_mbi,
                     sizeof(stack_mbi)) == 0 ||
        stack_mbi.AllocationBase == nullptr) {
        std::abort();
    }
    const auto allocation_base =
        reinterpret_cast<std::uintptr_t>(stack_mbi.AllocationBase);
    std::uintptr_t allocation_end = allocation_base;
    for (std::uintptr_t cursor = allocation_base;;) {
        MEMORY_BASIC_INFORMATION region{};
        if (VirtualQuery(reinterpret_cast<const void*>(cursor), &region, sizeof(region)) == 0 ||
            region.AllocationBase != stack_mbi.AllocationBase) {
            break;
        }
        const auto region_end = reinterpret_cast<std::uintptr_t>(region.BaseAddress) +
                                static_cast<std::uintptr_t>(region.RegionSize);
        if (region_end <= cursor) {
            break;
        }
        allocation_end = region_end;
        cursor = region_end;
    }
    if (guest->sp <= allocation_base || guest->sp > allocation_end) {
        std::abort();
    }

    ARM64_NT_CONTEXT bridge_context = context;
    bridge_context.Pc = reinterpret_cast<std::uint64_t>(&WindowsNceGuestStackBridge);
    bridge_context.X0 = reinterpret_cast<std::uint64_t>(&context);
    bridge_context.X[1] = static_cast<std::uint64_t>(allocation_end);
    bridge_context.X[2] = static_cast<std::uint64_t>(allocation_base);
    WindowsNceTransition::ContinueContext(bridge_context);
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

    auto* const nce = guest.parent;
    if (nce == nullptr || nce->m_windows_break == nullptr ||
        !nce->m_windows_break->IsBound()) {
        std::abort();
    }

    const auto host_pc = host.host_saved_regs[11];
    // Keep the guest SP through Windows exception/context resume. The bridge publishes
    // host TEB bounds first, then switches SP itself without re-entering the dispatcher.
    interrupted.Pc = reinterpret_cast<std::uint64_t>(&WindowsNceHostStackBridge);
    interrupted.X0 = return_value;
    interrupted.X[1] = static_cast<std::uint64_t>(nce->m_windows_break->HostStackHigh());
    interrupted.X[2] = static_cast<std::uint64_t>(nce->m_windows_break->HostStackLow());
    interrupted.X[3] = host.host_sp;
    interrupted.X[16] = host_pc;
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
