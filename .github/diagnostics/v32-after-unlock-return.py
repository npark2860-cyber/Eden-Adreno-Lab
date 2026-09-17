#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: v32-after-unlock-return.py <arm_nce_windows.cpp> <patcher.cpp> <windows_nce_transition.h> <windows_nce_entry.asm>"
    )

cpp_path = Path(sys.argv[1])
patcher_path = Path(sys.argv[2])
hdr_path = Path(sys.argv[3])
asm_path = Path(sys.argv[4])

cpp = cpp_path.read_text(encoding="utf-8")
patcher = patcher_path.read_text(encoding="utf-8")
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
    "v32-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV32ProbeFileName[] = "eden_nce_v32_after_unlock.log";
constexpr std::uintptr_t WindowsNceV32TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV32TargetTrampolineAllocationOffset = 0x1F25BC;

void WriteWindowsNceV32LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV32Line(const char* line) noexcept {
    WriteWindowsNceV32LineToPath(WindowsNceV32ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV32ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV32ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV32ProbeFileName[i];
    }
    WriteWindowsNceV32LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV32ProbeTarget(u64 pc, const void* trampoline) noexcept {
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

    return pc_value - pc_allocation == WindowsNceV32TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV32TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV32Probe(const char* marker, u64 pc, u64 sp,
                             const void* trampoline) noexcept {
    char line[384]{};
    std::snprintf(line, sizeof(line),
                  "%s pc=0x%016llX sp=0x%016llX trampoline=%p",
                  marker, static_cast<unsigned long long>(pc),
                  static_cast<unsigned long long>(sp), trampoline);
    WriteWindowsNceV32Line(line);
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "post-entry-probe",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
    """        bool v32_probe_returned = false;\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const actual_trampoline = reinterpret_cast<const void*>(it->second);\n            const bool v32_probe =\n                IsWindowsNceV32ProbeTarget(m_guest_ctx.pc, actual_trampoline);\n            if (v32_probe) {\n                WriteWindowsNceV32Probe(\"V32_PROBE_ENTER\", m_guest_ctx.pc, m_guest_ctx.sp,\n                                        actual_trampoline);\n            }\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, actual_trampoline));\n            if (v32_probe) {\n                WriteWindowsNceV32Probe(\"V32_AFTER_UNLOCK_RETURNED\", m_guest_ctx.pc,\n                                        m_guest_ctx.sp, actual_trampoline);\n                v32_probe_returned = true;\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n\n        if (v32_probe_returned) {\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
)

patcher = replace_once(
    patcher,
    "target-after-unlock",
    """    this->UnlockContext(cg);\n    cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n    cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n\n    if (is_pre)\n        this->BranchToModulePre(module_dest);\n    else\n        this->BranchToModule(module_dest);\n""",
    """    this->UnlockContext(cg);\n\n    // V32 diagnostic: for the one terminal post-SVC module offset proven by V29/V30, stop\n    // immediately after UnlockContext and return through the saved host continuation. This keeps\n    // the real WindowsNceEnterGuest restore, real trampoline entry and real UnlockContext path,\n    // while excluding guest x16/x17 reload plus the final direct branch-to-module.\n    if (module_dest == 0x1F03764) {\n        oaknut::Label v32_return_address;\n        cg.LDR(X15, v32_return_address);\n        cg.BR(X15);\n        cg.l(v32_return_address);\n        cg.dx(static_cast<u64>(reinterpret_cast<uintptr_t>(\n            &WindowsNceV32AfterUnlockReturn)));\n    } else {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n\n        if (is_pre)\n            this->BranchToModulePre(module_dest);\n        else\n            this->BranchToModule(module_dest);\n    }\n""",
)

hdr = replace_once(
    hdr,
    "probe-return-declaration",
    """extern \"C\" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,\n                                               const void* entry_trampoline) noexcept;\n""",
    """extern \"C\" std::uint64_t WindowsNceEnterGuest(GuestContext* guest,\n                                               const void* entry_trampoline) noexcept;\n\n// V32 diagnostic-only target reached from the selected generated post-SVC trampoline after its\n// real UnlockContext sequence has completed. x17 still carries GuestContext here.\nextern \"C\" std::uint64_t WindowsNceV32AfterUnlockReturn() noexcept;\n""",
)

asm = replace_once(
    asm,
    "probe-export",
    """        EXPORT  WindowsNceEnterGuest\n        EXPORT  WindowsNceEnterGuestContext\n""",
    """        EXPORT  WindowsNceEnterGuest\n        EXPORT  WindowsNceV32AfterUnlockReturn\n        EXPORT  WindowsNceEnterGuestContext\n""",
)

asm = replace_once(
    asm,
    "probe-return-proc",
    """        br      x16\n        ENDP\n\n; uint64_t WindowsNceEnterGuestContext(GuestContext* guest)\n""",
    """        br      x16\n        ENDP\n\n; V32 diagnostic-only controlled return after the selected generated trampoline completed\n; UnlockContext. x17 is still the GuestContext pointer because guest x17 has not been restored yet.\nWindowsNceV32AfterUnlockReturn PROC\n        add     x9, x17, #GuestContextHostContext\n        ldr     x10, [x9, #HostContextSp]\n        mov     sp, x10\n\n        ldp     x19, x20, [x9, #(HostContextRegs + 0x00)]\n        ldp     x21, x22, [x9, #(HostContextRegs + 0x10)]\n        ldp     x23, x24, [x9, #(HostContextRegs + 0x20)]\n        ldp     x25, x26, [x9, #(HostContextRegs + 0x30)]\n        ldp     x27, x28, [x9, #(HostContextRegs + 0x40)]\n        ldp     x29, x30, [x9, #(HostContextRegs + 0x50)]\n\n        ldp     q8,  q9,  [x9, #(HostContextVregs + 0x00)]\n        ldp     q10, q11, [x9, #(HostContextVregs + 0x20)]\n        ldp     q12, q13, [x9, #(HostContextVregs + 0x40)]\n        ldp     q14, q15, [x9, #(HostContextVregs + 0x60)]\n\n        mov     x0, xzr\n        ret\n        ENDP\n\n; uint64_t WindowsNceEnterGuestContext(GuestContext* guest)\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
patcher_path.write_text(patcher, encoding="utf-8", newline="\n")
hdr_path.write_text(hdr, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

for path, markers in [
    (cpp_path, [
        "eden_nce_v32_after_unlock.log",
        "V32_PROBE_ENTER",
        "V32_AFTER_UNLOCK_RETURNED",
        "WindowsNceV32TargetPcAllocationOffset",
    ]),
    (patcher_path, ["module_dest == 0x1F03764", "WindowsNceV32AfterUnlockReturn"]),
    (hdr_path, ["WindowsNceV32AfterUnlockReturn"]),
    (asm_path, ["EXPORT  WindowsNceV32AfterUnlockReturn", "WindowsNceV32AfterUnlockReturn PROC"]),
]:
    updated = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in updated:
            raise SystemExit(f"missing V32 marker in {path}: {marker}")

print("REALGAME_V32_AFTER_UNLOCK_RETURN=PASS")
