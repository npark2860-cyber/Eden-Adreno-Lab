#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v42-post-repair-exception.py <arm_nce_windows.cpp>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")


def r(label: str, old: str, new: str) -> None:
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n}")
    s = s.replace(old, new, 1)


r(
    "cstdio",
    "#include <atomic>\n#include <cstdint>\n",
    "#include <atomic>\n#include <cstdint>\n#include <cstdio>\n",
)

r(
    "helpers",
    "std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV42ProbeFileName[] = "eden_nce_v42_post_repair_exception.log";
constexpr std::uintptr_t WindowsNceV42TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV42TargetTrampolineAllocationOffset = 0x1F25BC;
thread_local u64 g_windows_nce_v42_seq{};
thread_local u64 g_windows_nce_v42_active_seq{};
thread_local bool g_windows_nce_v42_active{};
thread_local bool g_windows_nce_v42_repair_seen{};
thread_local bool g_windows_nce_v42_post_repair_exception_logged{};

void WriteWindowsNceV42LineToPath(const char* path, const char* line) noexcept {
    const HANDLE f = CreateFileA(path, FILE_APPEND_DATA,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                 nullptr, OPEN_ALWAYS,
                                 FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);
    if (f == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written{};
    const DWORD len = static_cast<DWORD>(lstrlenA(line));
    if (len != 0) {
        WriteFile(f, line, len, &written, nullptr);
        static constexpr char nl[] = "\r\n";
        WriteFile(f, nl, static_cast<DWORD>(sizeof(nl) - 1), &written, nullptr);
        FlushFileBuffers(f);
    }
    CloseHandle(f);
}

void WriteWindowsNceV42Line(const char* line) noexcept {
    WriteWindowsNceV42LineToPath(WindowsNceV42ProbeFileName, line);
    char temp[MAX_PATH]{};
    const DWORD n = GetTempPathA(MAX_PATH, temp);
    if (n == 0 || n >= MAX_PATH || n + sizeof(WindowsNceV42ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV42ProbeFileName); ++i) {
        temp[n + i] = WindowsNceV42ProbeFileName[i];
    }
    WriteWindowsNceV42LineToPath(temp, line);
}

[[nodiscard]] bool IsWindowsNceV42Target(u64 pc, const void* trampoline) noexcept {
    MEMORY_BASIC_INFORMATION a{};
    MEMORY_BASIC_INFORMATION b{};
    if (VirtualQuery(reinterpret_cast<const void*>(pc), &a, sizeof(a)) == 0 ||
        VirtualQuery(trampoline, &b, sizeof(b)) == 0 || a.AllocationBase == nullptr ||
        b.AllocationBase == nullptr) {
        return false;
    }
    const auto pv = static_cast<std::uintptr_t>(pc);
    const auto pa = reinterpret_cast<std::uintptr_t>(a.AllocationBase);
    const auto tv = reinterpret_cast<std::uintptr_t>(trampoline);
    const auto ta = reinterpret_cast<std::uintptr_t>(b.AllocationBase);
    return pv >= pa && tv >= ta && pv - pa == WindowsNceV42TargetPcAllocationOffset &&
           tv - ta == WindowsNceV42TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV42Entry(const char* marker, u64 seq, const GuestContext& guest,
                             const void* trampoline, u64 hr = 0) noexcept {
    char line[640]{};
    std::snprintf(line, sizeof(line),
                  "%s seq=%llu tid=%lu hr=0x%016llX pc=0x%016llX sp=0x%016llX "
                  "svc=0x%08X guest_x18=0x%016llX trampoline=%p",
                  marker, static_cast<unsigned long long>(seq),
                  static_cast<unsigned long>(GetCurrentThreadId()),
                  static_cast<unsigned long long>(hr),
                  static_cast<unsigned long long>(guest.pc),
                  static_cast<unsigned long long>(guest.sp),
                  static_cast<unsigned int>(guest.svc),
                  static_cast<unsigned long long>(guest.cpu_registers[18]), trampoline);
    WriteWindowsNceV42Line(line);
}

void WriteWindowsNceV42Repair(const ARM64_NT_CONTEXT& context, const GuestContext& guest,
                              u64 before_x18, u64 live_teb, bool redirected,
                              u32 lock) noexcept {
    char line[1024]{};
    std::snprintf(
        line, sizeof(line),
        "V42_X18_REPAIR seq=%llu tid=%lu redirected=%u lock=%u before_x18=0x%016llX "
        "live_teb=0x%016llX after_x18=0x%016llX context_pc=0x%016llX "
        "context_sp=0x%016llX x0=0x%016llX x1=0x%016llX x2=0x%016llX "
        "x3=0x%016llX x16=0x%016llX guest_pc=0x%016llX guest_sp=0x%016llX",
        static_cast<unsigned long long>(g_windows_nce_v42_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()), redirected ? 1U : 0U, lock,
        static_cast<unsigned long long>(before_x18),
        static_cast<unsigned long long>(live_teb),
        static_cast<unsigned long long>(context.X[18]),
        static_cast<unsigned long long>(context.Pc),
        static_cast<unsigned long long>(context.Sp),
        static_cast<unsigned long long>(context.X0),
        static_cast<unsigned long long>(context.X[1]),
        static_cast<unsigned long long>(context.X[2]),
        static_cast<unsigned long long>(context.X[3]),
        static_cast<unsigned long long>(context.X[16]),
        static_cast<unsigned long long>(guest.pc),
        static_cast<unsigned long long>(guest.sp));
    WriteWindowsNceV42Line(line);
}

void WriteWindowsNceV42PostRepairException(const EXCEPTION_RECORD& record,
                                            const ARM64_NT_CONTEXT& context,
                                            const GuestContext& guest,
                                            bool host_stack) noexcept {
    if (!g_windows_nce_v42_active || !g_windows_nce_v42_repair_seen ||
        g_windows_nce_v42_post_repair_exception_logged) {
        return;
    }
    g_windows_nce_v42_post_repair_exception_logged = true;
    const u64 live_teb = reinterpret_cast<u64>(NtCurrentTeb());
    const auto params = static_cast<unsigned int>(record.NumberParameters);
    const u64 info0 = params > 0 ? static_cast<u64>(record.ExceptionInformation[0]) : 0;
    const u64 info1 = params > 1 ? static_cast<u64>(record.ExceptionInformation[1]) : 0;
    const u64 info2 = params > 2 ? static_cast<u64>(record.ExceptionInformation[2]) : 0;
    char line[1400]{};
    std::snprintf(
        line, sizeof(line),
        "V42_POST_REPAIR_EXCEPTION seq=%llu tid=%lu code=0x%08lX flags=0x%08lX "
        "exception_addr=%p context_pc=0x%016llX context_sp=0x%016llX host_stack=%u "
        "context_x18=0x%016llX live_teb=0x%016llX x0=0x%016llX x1=0x%016llX "
        "x2=0x%016llX x3=0x%016llX x16=0x%016llX params=%u info0=0x%016llX "
        "info1=0x%016llX info2=0x%016llX guest_pc=0x%016llX guest_sp=0x%016llX "
        "guest_x18=0x%016llX",
        static_cast<unsigned long long>(g_windows_nce_v42_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()),
        static_cast<unsigned long>(record.ExceptionCode),
        static_cast<unsigned long>(record.ExceptionFlags), record.ExceptionAddress,
        static_cast<unsigned long long>(context.Pc),
        static_cast<unsigned long long>(context.Sp), host_stack ? 1U : 0U,
        static_cast<unsigned long long>(context.X[18]),
        static_cast<unsigned long long>(live_teb),
        static_cast<unsigned long long>(context.X0),
        static_cast<unsigned long long>(context.X[1]),
        static_cast<unsigned long long>(context.X[2]),
        static_cast<unsigned long long>(context.X[3]),
        static_cast<unsigned long long>(context.X[16]), params,
        static_cast<unsigned long long>(info0),
        static_cast<unsigned long long>(info1),
        static_cast<unsigned long long>(info2),
        static_cast<unsigned long long>(guest.pc),
        static_cast<unsigned long long>(guest.sp),
        static_cast<unsigned long long>(guest.cpu_registers[18]));
    WriteWindowsNceV42Line(line);
}

struct WindowsTebStackBounds {
''',
)

r(
    "veh-post-repair-observer",
    """    auto* const nce = guest->parent;
    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);

    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.
""",
    """    auto* const nce = guest->parent;
    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);

    if (g_windows_nce_v42_active && g_windows_nce_v42_repair_seen) {
        const bool host_stack = nce->m_windows_break != nullptr &&
                                nce->m_windows_break->IsHostStackPointer(context.Sp);
        WriteWindowsNceV42PostRepairException(*exception->ExceptionRecord, context, *guest,
                                              host_stack);
    }

    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.
""",
)

r(
    "claim-repair",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&
        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(
            context.Pc, process->GetPostHandlers()).has_value()) {
        params->lock.store(SpinLockLocked, std::memory_order_release);
        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(
            exception, *guest, process->GetPostHandlers());
        if (redirected) {
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        params->lock.store(SpinLockUnlocked, std::memory_order_release);
        return EXCEPTION_CONTINUE_SEARCH;
    }
""",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&
        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(
            context.Pc, process->GetPostHandlers()).has_value()) {
        params->lock.store(SpinLockLocked, std::memory_order_release);
        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(
            exception, *guest, process->GetPostHandlers());
        if (redirected) {
            if (g_windows_nce_v42_active) {
                const u64 before_x18 = context.X[18];
                const u64 live_teb = reinterpret_cast<u64>(NtCurrentTeb());
                context.X[18] = live_teb;
                g_windows_nce_v42_repair_seen = true;
                WriteWindowsNceV42Repair(
                    context, *guest, before_x18, live_teb, redirected,
                    params->lock.load(std::memory_order_relaxed));
            }
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        params->lock.store(SpinLockUnlocked, std::memory_order_release);
        return EXCEPTION_CONTINUE_SEARCH;
    }
""",
)

r(
    "entry",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(
                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));
        } else {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));
        }
""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {
            const auto* const trampoline = reinterpret_cast<const void*>(it->second);
            const bool probe = IsWindowsNceV42Target(m_guest_ctx.pc, trampoline);
            u64 seq = 0;
            if (probe) {
                seq = ++g_windows_nce_v42_seq;
                g_windows_nce_v42_active_seq = seq;
                g_windows_nce_v42_active = true;
                g_windows_nce_v42_repair_seen = false;
                g_windows_nce_v42_post_repair_exception_logged = false;
                WriteWindowsNceV42Entry(\"V42_ENTER\", seq, m_guest_ctx, trampoline);
            }
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(&m_guest_ctx, trampoline));
            if (probe) {
                WriteWindowsNceV42Entry(\"V42_RETURN\", seq, m_guest_ctx, trampoline,
                                        static_cast<u64>(hr));
                g_windows_nce_v42_active = false;
                g_windows_nce_v42_active_seq = 0;
                g_windows_nce_v42_repair_seen = false;
            }
        } else {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));
        }
""",
)

p.write_text(s, encoding="utf-8", newline="\n")
updated = p.read_text(encoding="utf-8")
for marker in [
    "V42_ENTER",
    "V42_RETURN",
    "V42_X18_REPAIR",
    "V42_POST_REPAIR_EXCEPTION",
    "g_windows_nce_v42_repair_seen",
    "eden_nce_v42_post_repair_exception.log",
]:
    if marker not in updated:
        raise SystemExit(f"missing marker {marker}")
for stale in ["V41_X18_REPAIR", "V40_CLAIM_PRE", "V39_BREAKPOINT", "V38_EXCEPTION"]:
    if stale in updated:
        raise SystemExit(f"stale marker {stale}")
print("REALGAME_V42_POST_REPAIR_EXCEPTION=PASS")
