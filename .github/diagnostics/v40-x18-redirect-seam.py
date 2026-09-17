#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v40-x18-redirect-seam.py <arm_nce_windows.cpp>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def r(label, old, new):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n}")
    s = s.replace(old, new, 1)

r("cstdio", "#include <atomic>\n#include <cstdint>\n", "#include <atomic>\n#include <cstdint>\n#include <cstdio>\n")

r("helpers", "std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n", r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV40ProbeFileName[] = "eden_nce_v40_x18_redirect_seam.log";
constexpr std::uintptr_t WindowsNceV40TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV40TargetTrampolineAllocationOffset = 0x1F25BC;
thread_local u64 g_windows_nce_v40_seq{};
thread_local u64 g_windows_nce_v40_active_seq{};
thread_local bool g_windows_nce_v40_active{};

void WriteWindowsNceV40LineToPath(const char* path, const char* line) noexcept {
    const HANDLE f = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                 nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);
    if (f == INVALID_HANDLE_VALUE) return;
    DWORD written{};
    const DWORD len = static_cast<DWORD>(lstrlenA(line));
    if (len) {
        WriteFile(f, line, len, &written, nullptr);
        static constexpr char nl[] = "\r\n";
        WriteFile(f, nl, static_cast<DWORD>(sizeof(nl) - 1), &written, nullptr);
        FlushFileBuffers(f);
    }
    CloseHandle(f);
}

void WriteWindowsNceV40Line(const char* line) noexcept {
    WriteWindowsNceV40LineToPath(WindowsNceV40ProbeFileName, line);
    char temp[MAX_PATH]{};
    const DWORD n = GetTempPathA(MAX_PATH, temp);
    if (!n || n >= MAX_PATH || n + sizeof(WindowsNceV40ProbeFileName) > MAX_PATH) return;
    for (DWORD i = 0; i < sizeof(WindowsNceV40ProbeFileName); ++i) temp[n + i] = WindowsNceV40ProbeFileName[i];
    WriteWindowsNceV40LineToPath(temp, line);
}

bool IsWindowsNceV40Target(u64 pc, const void* trampoline) noexcept {
    MEMORY_BASIC_INFORMATION a{}, b{};
    if (!VirtualQuery(reinterpret_cast<const void*>(pc), &a, sizeof(a)) ||
        !VirtualQuery(trampoline, &b, sizeof(b)) || !a.AllocationBase || !b.AllocationBase) return false;
    const auto pv = static_cast<std::uintptr_t>(pc);
    const auto pa = reinterpret_cast<std::uintptr_t>(a.AllocationBase);
    const auto tv = reinterpret_cast<std::uintptr_t>(trampoline);
    const auto ta = reinterpret_cast<std::uintptr_t>(b.AllocationBase);
    return pv >= pa && tv >= ta && pv - pa == WindowsNceV40TargetPcAllocationOffset &&
           tv - ta == WindowsNceV40TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV40Entry(const char* marker, u64 seq, const GuestContext& guest,
                             const void* trampoline, u64 hr = 0) noexcept {
    char line[640]{};
    std::snprintf(line, sizeof(line),
                  "%s seq=%llu tid=%lu hr=0x%016llX pc=0x%016llX sp=0x%016llX svc=0x%08X x18=0x%016llX trampoline=%p",
                  marker, static_cast<unsigned long long>(seq), static_cast<unsigned long>(GetCurrentThreadId()),
                  static_cast<unsigned long long>(hr), static_cast<unsigned long long>(guest.pc),
                  static_cast<unsigned long long>(guest.sp), static_cast<unsigned int>(guest.svc),
                  static_cast<unsigned long long>(guest.cpu_registers[18]), trampoline);
    WriteWindowsNceV40Line(line);
}

void WriteWindowsNceV40Redirect(const char* marker, const ARM64_NT_CONTEXT& c,
                                const GuestContext& guest, u32 lock, bool redirected) noexcept {
    char line[1024]{};
    std::snprintf(line, sizeof(line),
        "%s seq=%llu tid=%lu redirected=%u lock=%u context_pc=0x%016llX context_sp=0x%016llX "
        "x0=0x%016llX x1=0x%016llX x2=0x%016llX x3=0x%016llX x16=0x%016llX x18=0x%016llX "
        "guest_pc=0x%016llX guest_sp=0x%016llX guest_x18=0x%016llX esr=0x%016llX",
        marker, static_cast<unsigned long long>(g_windows_nce_v40_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()), redirected ? 1U : 0U, lock,
        static_cast<unsigned long long>(c.Pc), static_cast<unsigned long long>(c.Sp),
        static_cast<unsigned long long>(c.X0), static_cast<unsigned long long>(c.X[1]),
        static_cast<unsigned long long>(c.X[2]), static_cast<unsigned long long>(c.X[3]),
        static_cast<unsigned long long>(c.X[16]), static_cast<unsigned long long>(c.X[18]),
        static_cast<unsigned long long>(guest.pc), static_cast<unsigned long long>(guest.sp),
        static_cast<unsigned long long>(guest.cpu_registers[18]),
        static_cast<unsigned long long>(guest.esr_el1.load(std::memory_order_relaxed)));
    WriteWindowsNceV40Line(line);
}

struct WindowsTebStackBounds {
''')

r("claim", """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&
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
""", """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&
        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(
            context.Pc, process->GetPostHandlers()).has_value()) {
        if (g_windows_nce_v40_active) {
            WriteWindowsNceV40Redirect("V40_CLAIM_PRE", context, *guest,
                                       params->lock.load(std::memory_order_relaxed), false);
        }
        params->lock.store(SpinLockLocked, std::memory_order_release);
        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(
            exception, *guest, process->GetPostHandlers());
        if (g_windows_nce_v40_active) {
            WriteWindowsNceV40Redirect("V40_CLAIM_POST", context, *guest,
                                       params->lock.load(std::memory_order_relaxed), redirected);
        }
        if (redirected) {
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        params->lock.store(SpinLockUnlocked, std::memory_order_release);
        return EXCEPTION_CONTINUE_SEARCH;
    }
""")

r("entry", """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(
                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));
        } else {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));
        }
""", """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {
            const auto* const trampoline = reinterpret_cast<const void*>(it->second);
            const bool probe = IsWindowsNceV40Target(m_guest_ctx.pc, trampoline);
            u64 seq = 0;
            if (probe) {
                seq = ++g_windows_nce_v40_seq;
                g_windows_nce_v40_active_seq = seq;
                g_windows_nce_v40_active = true;
                WriteWindowsNceV40Entry("V40_ENTER", seq, m_guest_ctx, trampoline);
            }
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(&m_guest_ctx, trampoline));
            if (probe) {
                WriteWindowsNceV40Entry("V40_RETURN", seq, m_guest_ctx, trampoline, static_cast<u64>(hr));
                g_windows_nce_v40_active = false;
                g_windows_nce_v40_active_seq = 0;
            }
        } else {
            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));
        }
""")

p.write_text(s, encoding="utf-8", newline="\n")
for m in ["V40_ENTER", "V40_RETURN", "V40_CLAIM_PRE", "V40_CLAIM_POST", "eden_nce_v40_x18_redirect_seam.log"]:
    if m not in s: raise SystemExit(f"missing marker {m}")
for stale in ["V39_BREAKPOINT", "V38_EXCEPTION", "V37_ENTER", "V36_ENTER", "V35_BRANCH_AUDIT"]:
    if stale in s: raise SystemExit(f"stale marker {stale}")
print("REALGAME_V40_X18_REDIRECT_SEAM=PASS")
