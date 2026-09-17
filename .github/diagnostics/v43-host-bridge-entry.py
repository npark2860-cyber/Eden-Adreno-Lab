#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: v43-host-bridge-entry.py <arm_nce_windows.cpp> <windows_nce_entry.asm>")

cpp_path = Path(sys.argv[1])
asm_path = Path(sys.argv[2])
cpp = cpp_path.read_text(encoding="utf-8")
asm = asm_path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


cpp = replace_once(
    cpp,
    "includes",
    "#include <atomic>\n#include <cstdint>\n",
    "#include <atomic>\n#include <cstdint>\n#include <cstdio>\n#include <cstring>\n",
)

cpp = replace_once(
    cpp,
    "helpers",
    "std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v43_host_bridge_entry.log";
constexpr std::uintptr_t WindowsNceV43TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV43TargetTrampolineAllocationOffset = 0x1F25BC;
constexpr u32 WindowsNceV43BridgeBreakpointImmediate = 0xF043;
constexpr u32 WindowsNceV43BridgeBreakpointInstruction =
    0xD4200000u | (WindowsNceV43BridgeBreakpointImmediate << 5);
static_assert(WindowsNceV43BridgeBreakpointInstruction == 0xD43E0860u);

thread_local u64 g_windows_nce_v43_seq{};
thread_local u64 g_windows_nce_v43_active_seq{};
thread_local bool g_windows_nce_v43_active{};
thread_local bool g_windows_nce_v43_repair_seen{};
thread_local bool g_windows_nce_v43_bridge_entry_seen{};
thread_local bool g_windows_nce_v43_post_repair_exception_logged{};

void WriteWindowsNceV43LineToPath(const char* path, const char* line) noexcept {
    const HANDLE file = CreateFileA(
        path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written{};
    const DWORD length = static_cast<DWORD>(lstrlenA(line));
    if (length != 0) {
        WriteFile(file, line, length, &written, nullptr);
        static constexpr char Newline[] = "\r\n";
        WriteFile(file, Newline, static_cast<DWORD>(sizeof(Newline) - 1), &written, nullptr);
        FlushFileBuffers(file);
    }
    CloseHandle(file);
}

void WriteWindowsNceV43Line(const char* line) noexcept {
    WriteWindowsNceV43LineToPath(WindowsNceV43ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV43ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV43ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV43ProbeFileName[i];
    }
    WriteWindowsNceV43LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV43Target(u64 pc, const void* trampoline) noexcept {
    MEMORY_BASIC_INFORMATION pc_mbi{};
    MEMORY_BASIC_INFORMATION tramp_mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(pc), &pc_mbi, sizeof(pc_mbi)) == 0 ||
        VirtualQuery(trampoline, &tramp_mbi, sizeof(tramp_mbi)) == 0 ||
        pc_mbi.AllocationBase == nullptr || tramp_mbi.AllocationBase == nullptr) {
        return false;
    }
    const auto pc_value = static_cast<std::uintptr_t>(pc);
    const auto pc_allocation = reinterpret_cast<std::uintptr_t>(pc_mbi.AllocationBase);
    const auto trampoline_value = reinterpret_cast<std::uintptr_t>(trampoline);
    const auto trampoline_allocation = reinterpret_cast<std::uintptr_t>(tramp_mbi.AllocationBase);
    return pc_value >= pc_allocation && trampoline_value >= trampoline_allocation &&
           pc_value - pc_allocation == WindowsNceV43TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV43TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV43Entry(const char* marker, u64 seq, const GuestContext& guest,
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
    WriteWindowsNceV43Line(line);
}

void WriteWindowsNceV43Repair(const ARM64_NT_CONTEXT& context, const GuestContext& guest,
                              u64 before_x18, u64 live_teb, bool redirected,
                              u32 lock) noexcept {
    char line[1024]{};
    std::snprintf(
        line, sizeof(line),
        "V43_X18_REPAIR seq=%llu tid=%lu redirected=%u lock=%u before_x18=0x%016llX "
        "live_teb=0x%016llX after_x18=0x%016llX context_pc=0x%016llX "
        "context_sp=0x%016llX x0=0x%016llX x1=0x%016llX x2=0x%016llX "
        "x3=0x%016llX x16=0x%016llX guest_pc=0x%016llX guest_sp=0x%016llX",
        static_cast<unsigned long long>(g_windows_nce_v43_active_seq),
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
    WriteWindowsNceV43Line(line);
}

void WriteWindowsNceV43BridgeEntry(const ARM64_NT_CONTEXT& context, u64 before_x18,
                                   u64 live_teb) noexcept {
    char line[900]{};
    std::snprintf(
        line, sizeof(line),
        "V43_BRIDGE_ENTRY seq=%llu tid=%lu context_pc=0x%016llX context_sp=0x%016llX "
        "before_x18=0x%016llX live_teb=0x%016llX after_x18=0x%016llX "
        "x0=0x%016llX x1=0x%016llX x2=0x%016llX x3=0x%016llX x16=0x%016llX",
        static_cast<unsigned long long>(g_windows_nce_v43_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()),
        static_cast<unsigned long long>(context.Pc),
        static_cast<unsigned long long>(context.Sp),
        static_cast<unsigned long long>(before_x18),
        static_cast<unsigned long long>(live_teb),
        static_cast<unsigned long long>(context.X[18]),
        static_cast<unsigned long long>(context.X0),
        static_cast<unsigned long long>(context.X[1]),
        static_cast<unsigned long long>(context.X[2]),
        static_cast<unsigned long long>(context.X[3]),
        static_cast<unsigned long long>(context.X[16]));
    WriteWindowsNceV43Line(line);
}

void WriteWindowsNceV43PostRepairException(const EXCEPTION_RECORD& record,
                                            const ARM64_NT_CONTEXT& context,
                                            const GuestContext& guest) noexcept {
    if (g_windows_nce_v43_post_repair_exception_logged) {
        return;
    }
    g_windows_nce_v43_post_repair_exception_logged = true;
    char line[1200]{};
    std::snprintf(
        line, sizeof(line),
        "V43_POST_REPAIR_EXCEPTION seq=%llu tid=%lu bridge_entry_seen=%u code=0x%08lX "
        "exception_addr=%p context_pc=0x%016llX context_sp=0x%016llX context_x18=0x%016llX "
        "live_teb=0x%016llX x0=0x%016llX x1=0x%016llX x2=0x%016llX x3=0x%016llX "
        "x16=0x%016llX guest_pc=0x%016llX guest_sp=0x%016llX",
        static_cast<unsigned long long>(g_windows_nce_v43_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()),
        g_windows_nce_v43_bridge_entry_seen ? 1U : 0U,
        static_cast<unsigned long>(record.ExceptionCode), record.ExceptionAddress,
        static_cast<unsigned long long>(context.Pc),
        static_cast<unsigned long long>(context.Sp),
        static_cast<unsigned long long>(context.X[18]),
        static_cast<unsigned long long>(reinterpret_cast<u64>(NtCurrentTeb())),
        static_cast<unsigned long long>(context.X0),
        static_cast<unsigned long long>(context.X[1]),
        static_cast<unsigned long long>(context.X[2]),
        static_cast<unsigned long long>(context.X[3]),
        static_cast<unsigned long long>(context.X[16]),
        static_cast<unsigned long long>(guest.pc),
        static_cast<unsigned long long>(guest.sp));
    WriteWindowsNceV43Line(line);
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "veh-bridge-entry",
    """    auto* const nce = guest->parent;\n    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);\n\n    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.\n""",
    """    auto* const nce = guest->parent;\n    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);\n\n    if (g_windows_nce_v43_active && g_windows_nce_v43_repair_seen &&\n        exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT) {\n        u32 instruction_word{};\n        MEMORY_BASIC_INFORMATION mbi{};\n        if (VirtualQuery(reinterpret_cast<const void*>(context.Pc), &mbi, sizeof(mbi)) != 0 &&\n            mbi.State == MEM_COMMIT && (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) == 0) {\n            std::memcpy(&instruction_word, reinterpret_cast<const void*>(context.Pc),\n                        sizeof(instruction_word));\n        }\n        if (instruction_word == WindowsNceV43BridgeBreakpointInstruction) {\n            const u64 before_x18 = context.X[18];\n            const u64 live_teb = reinterpret_cast<u64>(NtCurrentTeb());\n            context.X[18] = live_teb;\n            WriteWindowsNceV43BridgeEntry(context, before_x18, live_teb);\n            g_windows_nce_v43_bridge_entry_seen = true;\n            context.Pc += sizeof(u32);\n            return EXCEPTION_CONTINUE_EXECUTION;\n        }\n    }\n\n    if (g_windows_nce_v43_active && g_windows_nce_v43_repair_seen &&\n        !g_windows_nce_v43_post_repair_exception_logged) {\n        WriteWindowsNceV43PostRepairException(*exception->ExceptionRecord, context, *guest);\n    }\n\n    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.\n""",
)

cpp = replace_once(
    cpp,
    "claim-repair",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&\n        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(\n            context.Pc, process->GetPostHandlers()).has_value()) {\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(\n            exception, *guest, process->GetPostHandlers());\n        if (redirected) {\n            return EXCEPTION_CONTINUE_EXECUTION;\n        }\n        params->lock.store(SpinLockUnlocked, std::memory_order_release);\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&\n        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(\n            context.Pc, process->GetPostHandlers()).has_value()) {\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(\n            exception, *guest, process->GetPostHandlers());\n        if (redirected) {\n            if (g_windows_nce_v43_active) {\n                const u64 before_x18 = context.X[18];\n                const u64 live_teb = reinterpret_cast<u64>(NtCurrentTeb());\n                context.X[18] = live_teb;\n                g_windows_nce_v43_repair_seen = true;\n                WriteWindowsNceV43Repair(\n                    context, *guest, before_x18, live_teb, redirected,\n                    params->lock.load(std::memory_order_relaxed));\n            }\n            return EXCEPTION_CONTINUE_EXECUTION;\n        }\n        params->lock.store(SpinLockUnlocked, std::memory_order_release);\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
)

cpp = replace_once(
    cpp,
    "entry",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const trampoline = reinterpret_cast<const void*>(it->second);\n            const bool probe = IsWindowsNceV43Target(m_guest_ctx.pc, trampoline);\n            u64 seq = 0;\n            if (probe) {\n                seq = ++g_windows_nce_v43_seq;\n                g_windows_nce_v43_active_seq = seq;\n                g_windows_nce_v43_active = true;\n                g_windows_nce_v43_repair_seen = false;\n                g_windows_nce_v43_bridge_entry_seen = false;\n                g_windows_nce_v43_post_repair_exception_logged = false;\n                WriteWindowsNceV43Entry(\"V43_ENTER\", seq, m_guest_ctx, trampoline);\n            }\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(&m_guest_ctx, trampoline));\n            if (probe) {\n                WriteWindowsNceV43Entry(\"V43_RETURN\", seq, m_guest_ctx, trampoline,\n                                        static_cast<u64>(hr));\n                g_windows_nce_v43_active = false;\n                g_windows_nce_v43_active_seq = 0;\n                g_windows_nce_v43_repair_seen = false;\n                g_windows_nce_v43_bridge_entry_seen = false;\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n""",
)

asm = replace_once(
    asm,
    "bridge-entry-brk",
    """WindowsNceHostStackBridge PROC\n        str     x1, [x18, #8]\n""",
    """WindowsNceHostStackBridge PROC\n        brk     #61507\n        str     x1, [x18, #8]\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

updated_cpp = cpp_path.read_text(encoding="utf-8")
updated_asm = asm_path.read_text(encoding="utf-8")
for marker in [
    "V43_ENTER",
    "V43_RETURN",
    "V43_X18_REPAIR",
    "V43_BRIDGE_ENTRY",
    "V43_POST_REPAIR_EXCEPTION",
    "WindowsNceV43BridgeBreakpointInstruction",
    "eden_nce_v43_host_bridge_entry.log",
]:
    if marker not in updated_cpp:
        raise SystemExit(f"missing V43 marker in {cpp_path}: {marker}")
if "brk     #61507" not in updated_asm:
    raise SystemExit("missing V43 bridge-entry BRK")
for stale in ["V42_X18_REPAIR", "V41_X18_REPAIR", "V40_CLAIM_PRE", "V39_BREAKPOINT"]:
    if stale in updated_cpp:
        raise SystemExit(f"unexpected prior diagnostic marker in V43 source: {stale}")

print("REALGAME_V43_HOST_BRIDGE_ENTRY=PASS")
