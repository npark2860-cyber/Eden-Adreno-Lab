#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit(
        "usage: v31-direct-entry-bypass.py <arm_nce_windows.cpp> <windows_nce_transition.h> <windows_nce_entry.asm>"
    )

cpp_path = Path(sys.argv[1])
hdr_path = Path(sys.argv[2])
asm_path = Path(sys.argv[3])

cpp = cpp_path.read_text(encoding="utf-8")
hdr = hdr_path.read_text(encoding="utf-8")
asm = asm_path.read_text(encoding="utf-8")


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
    "v31-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV31ProbeFileName[] = "eden_nce_v31_direct_entry_bypass.log";
constexpr std::uintptr_t WindowsNceV31TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV31TargetTrampolineAllocationOffset = 0x1F25BC;

void WriteWindowsNceV31LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV31Line(const char* line) noexcept {
    WriteWindowsNceV31LineToPath(WindowsNceV31ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV31ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV31ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV31ProbeFileName[i];
    }
    WriteWindowsNceV31LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV31ProbeTarget(u64 pc, const void* trampoline) noexcept {
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

    return pc_value - pc_allocation == WindowsNceV31TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV31TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV31Probe(const char* marker, u64 pc, u64 sp,
                             const void* trampoline) noexcept {
    char line[384]{};
    std::snprintf(line, sizeof(line),
                  "%s pc=0x%016llX sp=0x%016llX trampoline=%p",
                  marker, static_cast<unsigned long long>(pc),
                  static_cast<unsigned long long>(sp), trampoline);
    WriteWindowsNceV31Line(line);
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "post-entry-probe",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
    """        bool v31_probe_returned = false;\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const actual_trampoline = reinterpret_cast<const void*>(it->second);\n            const bool v31_probe =\n                IsWindowsNceV31ProbeTarget(m_guest_ctx.pc, actual_trampoline);\n            if (v31_probe) {\n                WriteWindowsNceV31Probe(\"V31_PROBE_ENTER\", m_guest_ctx.pc, m_guest_ctx.sp,\n                                        actual_trampoline);\n            }\n            const void* const dispatch_trampoline =\n                v31_probe ? reinterpret_cast<const void*>(&NCE::WindowsNceV31ProbeReturn)\n                          : actual_trampoline;\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, dispatch_trampoline));\n            if (v31_probe) {\n                WriteWindowsNceV31Probe(\"V31_PROBE_RETURNED\", m_guest_ctx.pc, m_guest_ctx.sp,\n                                        actual_trampoline);\n                v31_probe_returned = true;\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n\n        if (v31_probe_returned) {\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
)

hdr = replace_once(
    hdr,
    "probe-return-declaration",
    """extern \"C\" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,\n                                               const void* entry_trampoline) noexcept;\n\n// Windows ARM64 arbitrary-PC entry.\n""",
    """extern \"C\" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,\n                                               const void* entry_trampoline) noexcept;\n\n// V31 diagnostic-only target. WindowsNceEnterGuest branches here only for the selected terminal\n// post-handler target. Guest register/SP restoration has already completed; this bridge restores\n// the saved host ABI continuation and returns without executing the generated post-entry code.\nextern \"C\" std::uint64_t WindowsNceV31ProbeReturn() noexcept;\n\n// Windows ARM64 arbitrary-PC entry.\n""",
)

asm = replace_once(
    asm,
    "probe-export",
    """        EXPORT  WindowsNceEnterGuest\n        EXPORT  WindowsNceEnterGuestContext\n""",
    """        EXPORT  WindowsNceEnterGuest\n        EXPORT  WindowsNceV31ProbeReturn\n        EXPORT  WindowsNceEnterGuestContext\n""",
)

asm = replace_once(
    asm,
    "probe-return-proc",
    """        br      x16\n        ENDP\n\n; uint64_t WindowsNceEnterGuestContext(GuestContext* guest)\n""",
    """        br      x16\n        ENDP\n\n; V31 diagnostic-only controlled return target. WindowsNceEnterGuest has already restored guest\n; architectural state and switched to guest SP before branching here. x17 still carries the\n; GuestContext pointer because only the generated post-entry trampoline normally restores guest x17.\nWindowsNceV31ProbeReturn PROC\n        add     x9, x17, #GuestContextHostContext\n        ldr     x10, [x9, #HostContextSp]\n        mov     sp, x10\n\n        ldp     x19, x20, [x9, #(HostContextRegs + 0x00)]\n        ldp     x21, x22, [x9, #(HostContextRegs + 0x10)]\n        ldp     x23, x24, [x9, #(HostContextRegs + 0x20)]\n        ldp     x25, x26, [x9, #(HostContextRegs + 0x30)]\n        ldp     x27, x28, [x9, #(HostContextRegs + 0x40)]\n        ldp     x29, x30, [x9, #(HostContextRegs + 0x50)]\n\n        ldp     q8,  q9,  [x9, #(HostContextVregs + 0x00)]\n        ldp     q10, q11, [x9, #(HostContextVregs + 0x20)]\n        ldp     q12, q13, [x9, #(HostContextVregs + 0x40)]\n        ldp     q14, q15, [x9, #(HostContextVregs + 0x60)]\n\n        mov     x0, xzr\n        ret\n        ENDP\n\n; uint64_t WindowsNceEnterGuestContext(GuestContext* guest)\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
hdr_path.write_text(hdr, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

for path, markers in [
    (cpp_path, [
        "eden_nce_v31_direct_entry_bypass.log",
        "V31_PROBE_ENTER",
        "V31_PROBE_RETURNED",
        "WindowsNceV31TargetPcAllocationOffset",
        "WindowsNceV31ProbeReturn",
    ]),
    (hdr_path, ["WindowsNceV31ProbeReturn"]),
    (asm_path, ["EXPORT  WindowsNceV31ProbeReturn", "WindowsNceV31ProbeReturn PROC"]),
]:
    updated = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in updated:
            raise SystemExit(f"missing V31 marker in {path}: {marker}")

print("REALGAME_V31_DIRECT_ENTRY_BYPASS=PASS")
