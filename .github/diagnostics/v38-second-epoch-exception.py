#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v38-second-epoch-exception.py <arm_nce_windows.cpp>")

cpp_path = Path(sys.argv[1])
cpp = cpp_path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


cpp = replace_once(
    cpp,
    "cstdio-include",
    """#include <atomic>\n#include <cstdint>\n""",
    """#include <atomic>\n#include <cstdint>\n#include <cstdio>\n""",
)

cpp = replace_once(
    cpp,
    "v38-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV38ProbeFileName[] = "eden_nce_v38_second_epoch_exception.log";
constexpr std::uintptr_t WindowsNceV38TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV38TargetTrampolineAllocationOffset = 0x1F25BC;

thread_local u64 g_windows_nce_v38_selected_seq{};
thread_local u64 g_windows_nce_v38_active_seq{};
thread_local bool g_windows_nce_v38_active{};
thread_local bool g_windows_nce_v38_logging_exception{};

void WriteWindowsNceV38LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV38Line(const char* line) noexcept {
    WriteWindowsNceV38LineToPath(WindowsNceV38ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV38ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV38ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV38ProbeFileName[i];
    }
    WriteWindowsNceV38LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV38ProbeTarget(u64 pc, const void* trampoline) noexcept {
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
    if (pc_value < pc_allocation || trampoline_value < trampoline_allocation) {
        return false;
    }

    return pc_value - pc_allocation == WindowsNceV38TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV38TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV38Entry(const char* marker, u64 seq, const GuestContext& guest,
                             const void* trampoline) noexcept {
    char line[640]{};
    std::snprintf(
        line, sizeof(line),
        "%s seq=%llu tid=%lu pc=0x%016llX sp=0x%016llX svc=0x%08X "
        "x0=0x%016llX x1=0x%016llX x16=0x%016llX x17=0x%016llX "
        "x18=0x%016llX x29=0x%016llX x30=0x%016llX trampoline=%p",
        marker, static_cast<unsigned long long>(seq),
        static_cast<unsigned long>(GetCurrentThreadId()),
        static_cast<unsigned long long>(guest.pc), static_cast<unsigned long long>(guest.sp),
        static_cast<unsigned int>(guest.svc),
        static_cast<unsigned long long>(guest.cpu_registers[0]),
        static_cast<unsigned long long>(guest.cpu_registers[1]),
        static_cast<unsigned long long>(guest.cpu_registers[16]),
        static_cast<unsigned long long>(guest.cpu_registers[17]),
        static_cast<unsigned long long>(guest.cpu_registers[18]),
        static_cast<unsigned long long>(guest.cpu_registers[29]),
        static_cast<unsigned long long>(guest.cpu_registers[30]), trampoline);
    WriteWindowsNceV38Line(line);
}

void WriteWindowsNceV38Exception(const EXCEPTION_RECORD& record,
                                 const ARM64_NT_CONTEXT& context,
                                 const GuestContext& guest, bool host_stack) noexcept {
    if (g_windows_nce_v38_logging_exception) {
        return;
    }
    g_windows_nce_v38_logging_exception = true;

    const ULONG_PTR info0 = record.NumberParameters > 0 ? record.ExceptionInformation[0] : 0;
    const ULONG_PTR info1 = record.NumberParameters > 1 ? record.ExceptionInformation[1] : 0;
    const ULONG_PTR info2 = record.NumberParameters > 2 ? record.ExceptionInformation[2] : 0;
    char line[1280]{};
    std::snprintf(
        line, sizeof(line),
        "V38_EXCEPTION seq=%llu tid=%lu code=0x%08lX flags=0x%08lX exception_addr=%p "
        "context_pc=0x%016llX context_sp=0x%016llX host_stack=%u params=%lu "
        "info0=0x%016llX info1=0x%016llX info2=0x%016llX "
        "ctx_x0=0x%016llX ctx_x1=0x%016llX ctx_x16=0x%016llX ctx_x17=0x%016llX "
        "ctx_x18=0x%016llX ctx_x29=0x%016llX ctx_x30=0x%016llX "
        "guest_pc=0x%016llX guest_sp=0x%016llX guest_svc=0x%08X",
        static_cast<unsigned long long>(g_windows_nce_v38_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()),
        static_cast<unsigned long>(record.ExceptionCode),
        static_cast<unsigned long>(record.ExceptionFlags), record.ExceptionAddress,
        static_cast<unsigned long long>(context.Pc), static_cast<unsigned long long>(context.Sp),
        host_stack ? 1U : 0U, static_cast<unsigned long>(record.NumberParameters),
        static_cast<unsigned long long>(info0), static_cast<unsigned long long>(info1),
        static_cast<unsigned long long>(info2),
        static_cast<unsigned long long>(context.X0), static_cast<unsigned long long>(context.X1),
        static_cast<unsigned long long>(context.X16), static_cast<unsigned long long>(context.X17),
        static_cast<unsigned long long>(context.X18), static_cast<unsigned long long>(context.Fp),
        static_cast<unsigned long long>(context.Lr), static_cast<unsigned long long>(guest.pc),
        static_cast<unsigned long long>(guest.sp), static_cast<unsigned int>(guest.svc));
    WriteWindowsNceV38Line(line);
    g_windows_nce_v38_logging_exception = false;
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "v38-veh-observer",
    """    auto* const nce = guest->parent;\n    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);\n\n    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.\n""",
    """    auto* const nce = guest->parent;\n    auto& context = *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord);\n\n    if (g_windows_nce_v38_active) {\n        const bool v38_host_stack =\n            nce->m_windows_break != nullptr && nce->m_windows_break->IsHostStackPointer(context.Sp);\n        WriteWindowsNceV38Exception(*exception->ExceptionRecord, context, *guest,\n                                    v38_host_stack);\n    }\n\n    // The Windows transition and arbitrary-PC restore helpers execute on the original host stack.\n""",
)

cpp = replace_once(
    cpp,
    "v38-entry-observer",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const actual_trampoline = reinterpret_cast<const void*>(it->second);\n            const bool v38_probe = IsWindowsNceV38ProbeTarget(m_guest_ctx.pc, actual_trampoline);\n            u64 v38_seq = 0;\n            if (v38_probe) {\n                v38_seq = ++g_windows_nce_v38_selected_seq;\n                g_windows_nce_v38_active_seq = v38_seq;\n                g_windows_nce_v38_active = true;\n                WriteWindowsNceV38Entry(\"V38_ENTER\", v38_seq, m_guest_ctx, actual_trampoline);\n            }\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, actual_trampoline));\n            if (v38_probe) {\n                WriteWindowsNceV38Entry(\"V38_RETURN\", v38_seq, m_guest_ctx, actual_trampoline);\n                g_windows_nce_v38_active = false;\n                g_windows_nce_v38_active_seq = 0;\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")

updated = cpp_path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v38_second_epoch_exception.log",
    "V38_ENTER",
    "V38_RETURN",
    "V38_EXCEPTION",
    "WindowsNceV38TargetPcAllocationOffset",
    "g_windows_nce_v38_active",
]:
    if marker not in updated:
        raise SystemExit(f"missing V38 marker in {cpp_path}: {marker}")

for stale in ["V37_EPOCH", "V36_PENDING", "V35_BRANCH_AUDIT"]:
    if stale in updated:
        raise SystemExit(f"unexpected prior diagnostic marker in V38 source: {stale}")

print("REALGAME_V38_SECOND_EPOCH_EXCEPTION=PASS")
