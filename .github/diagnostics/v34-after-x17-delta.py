#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: v34-after-x17-delta.py <arm_nce_windows.cpp> <patcher.cpp> <windows_nce_transition.h> <windows_nce_entry.asm>"
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


for old, new in [
    ("WindowsNceV33ProbeFileName", "WindowsNceV34ProbeFileName"),
    ("WindowsNceV33TargetPcAllocationOffset", "WindowsNceV34TargetPcAllocationOffset"),
    ("WindowsNceV33TargetTrampolineAllocationOffset", "WindowsNceV34TargetTrampolineAllocationOffset"),
    ("WriteWindowsNceV33LineToPath", "WriteWindowsNceV34LineToPath"),
    ("WriteWindowsNceV33Line", "WriteWindowsNceV34Line"),
    ("IsWindowsNceV33ProbeTarget", "IsWindowsNceV34ProbeTarget"),
    ("WriteWindowsNceV33Probe", "WriteWindowsNceV34Probe"),
    ("v33_probe_returned", "v34_probe_returned"),
    ("v33_probe", "v34_probe"),
    ("V33_PROBE_ENTER", "V34_PROBE_ENTER"),
    ("V33_AFTER_X16_RETURNED", "V34_AFTER_X17_RETURNED"),
    ("eden_nce_v33_after_x16.log", "eden_nce_v34_after_x17.log"),
]:
    if old not in cpp:
        raise SystemExit(f"cpp rename source missing: {old}")
    cpp = cpp.replace(old, new)

old_block = """    this->UnlockContext(cg);\n\n    // V33 diagnostic: execute the real guest-x16 reload after the proven UnlockContext path, then\n    // return through the saved host continuation while x17 still carries GuestContext. Guest x17\n    // reload and the final direct branch-to-module remain excluded.\n    if (module_dest == 0x1F03764) {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        oaknut::Label v33_return_address;\n        cg.LDR(X15, v33_return_address);\n        cg.BR(X15);\n        cg.l(v33_return_address);\n        cg.dx(static_cast<u64>(reinterpret_cast<uintptr_t>(\n            &WindowsNceV33AfterX16Return)));\n    } else {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n\n        if (is_pre)\n            this->BranchToModulePre(module_dest);\n        else\n            this->BranchToModule(module_dest);\n    }\n"""
new_block = """    this->UnlockContext(cg);\n\n    // V34 diagnostic: execute the real guest-x16 and guest-x17 reloads after the proven\n    // UnlockContext path. Preserve the GuestContext pointer in x15 only for this controlled\n    // diagnostic return; the final direct branch-to-module remains excluded.\n    if (module_dest == 0x1F03764) {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        cg.MOV(X15, X17);\n        cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n        oaknut::Label v34_return_address;\n        cg.LDR(X14, v34_return_address);\n        cg.BR(X14);\n        cg.l(v34_return_address);\n        cg.dx(static_cast<u64>(reinterpret_cast<uintptr_t>(\n            &WindowsNceV34AfterX17Return)));\n    } else {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n\n        if (is_pre)\n            this->BranchToModulePre(module_dest);\n        else\n            this->BranchToModule(module_dest);\n    }\n"""
patcher = replace_once(patcher, "v34-after-x17-block", old_block, new_block)

hdr = replace_once(hdr, "v34-header-symbol", "WindowsNceV33AfterX16Return",
                   "WindowsNceV34AfterX17Return")
hdr = hdr.replace(
    "V33 diagnostic-only target reached from the selected generated post-SVC trampoline after its\n// real UnlockContext sequence and guest-x16 reload have completed. x17 still carries GuestContext here.",
    "V34 diagnostic-only target reached from the selected generated post-SVC trampoline after its\n// real UnlockContext sequence and guest-x16/x17 reloads have completed. x15 carries GuestContext only for this diagnostic return.",
)

asm = replace_once(asm, "v34-asm-export", "EXPORT  WindowsNceV33AfterX16Return",
                   "EXPORT  WindowsNceV34AfterX17Return")
asm = replace_once(asm, "v34-asm-proc", "WindowsNceV33AfterX16Return PROC",
                   "WindowsNceV34AfterX17Return PROC")
asm = asm.replace(
    "; V33 diagnostic-only controlled return after the selected generated trampoline completed\n; UnlockContext and guest-x16 reload. x17 is still GuestContext because guest x17 is not restored yet.",
    "; V34 diagnostic-only controlled return after the selected generated trampoline completed\n; UnlockContext and guest-x16/x17 reloads. x15 carries GuestContext only for this diagnostic return.",
)
asm = replace_once(
    asm,
    "v34-context-carrier",
    """WindowsNceV34AfterX17Return PROC\n        add     x9, x17, #GuestContextHostContext\n""",
    """WindowsNceV34AfterX17Return PROC\n        add     x9, x15, #GuestContextHostContext\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
patcher_path.write_text(patcher, encoding="utf-8", newline="\n")
hdr_path.write_text(hdr, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

for path, markers in [
    (cpp_path, ["eden_nce_v34_after_x17.log", "V34_PROBE_ENTER", "V34_AFTER_X17_RETURNED",
                "WindowsNceV34TargetPcAllocationOffset"]),
    (patcher_path, ["module_dest == 0x1F03764", "WindowsNceV34AfterX17Return",
                    "cg.MOV(X15, X17);",
                    "cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);"]),
    (hdr_path, ["WindowsNceV34AfterX17Return"]),
    (asm_path, ["EXPORT  WindowsNceV34AfterX17Return", "WindowsNceV34AfterX17Return PROC",
                "add     x9, x15, #GuestContextHostContext"]),
]:
    updated = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in updated:
            raise SystemExit(f"missing V34 marker in {path}: {marker}")

for old_marker in ["V33_PROBE_ENTER", "V33_AFTER_X16_RETURNED", "WindowsNceV33AfterX16Return"]:
    for path in (cpp_path, patcher_path, hdr_path, asm_path):
        if old_marker in path.read_text(encoding="utf-8"):
            raise SystemExit(f"stale V33 marker in {path}: {old_marker}")

print("REALGAME_V34_AFTER_X17_RETURN=PASS")
