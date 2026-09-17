#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: v33-after-x16-delta.py <arm_nce_windows.cpp> <patcher.cpp> <windows_nce_transition.h> <windows_nce_entry.asm>"
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
    ("WindowsNceV32ProbeFileName", "WindowsNceV33ProbeFileName"),
    ("WindowsNceV32TargetPcAllocationOffset", "WindowsNceV33TargetPcAllocationOffset"),
    ("WindowsNceV32TargetTrampolineAllocationOffset", "WindowsNceV33TargetTrampolineAllocationOffset"),
    ("WriteWindowsNceV32LineToPath", "WriteWindowsNceV33LineToPath"),
    ("WriteWindowsNceV32Line", "WriteWindowsNceV33Line"),
    ("IsWindowsNceV32ProbeTarget", "IsWindowsNceV33ProbeTarget"),
    ("WriteWindowsNceV32Probe", "WriteWindowsNceV33Probe"),
    ("v32_probe_returned", "v33_probe_returned"),
    ("v32_probe", "v33_probe"),
    ("V32_PROBE_ENTER", "V33_PROBE_ENTER"),
    ("V32_AFTER_UNLOCK_RETURNED", "V33_AFTER_X16_RETURNED"),
    ("eden_nce_v32_after_unlock.log", "eden_nce_v33_after_x16.log"),
]:
    if old not in cpp:
        raise SystemExit(f"cpp rename source missing: {old}")
    cpp = cpp.replace(old, new)

old_block = """    this->UnlockContext(cg);\n\n    // V32 diagnostic: for the one terminal post-SVC module offset proven by V29/V30, stop\n    // immediately after UnlockContext and return through the saved host continuation. This keeps\n    // the real WindowsNceEnterGuest restore, real trampoline entry and real UnlockContext path,\n    // while excluding guest x16/x17 reload plus the final direct branch-to-module.\n    if (module_dest == 0x1F03764) {\n        oaknut::Label v32_return_address;\n        cg.LDR(X15, v32_return_address);\n        cg.BR(X15);\n        cg.l(v32_return_address);\n        cg.dx(static_cast<u64>(reinterpret_cast<uintptr_t>(\n            &WindowsNceV32AfterUnlockReturn)));\n    } else {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n\n        if (is_pre)\n            this->BranchToModulePre(module_dest);\n        else\n            this->BranchToModule(module_dest);\n    }\n"""
new_block = """    this->UnlockContext(cg);\n\n    // V33 diagnostic: execute the real guest-x16 reload after the proven UnlockContext path, then\n    // return through the saved host continuation while x17 still carries GuestContext. Guest x17\n    // reload and the final direct branch-to-module remain excluded.\n    if (module_dest == 0x1F03764) {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        oaknut::Label v33_return_address;\n        cg.LDR(X15, v33_return_address);\n        cg.BR(X15);\n        cg.l(v33_return_address);\n        cg.dx(static_cast<u64>(reinterpret_cast<uintptr_t>(\n            &WindowsNceV33AfterX16Return)));\n    } else {\n        cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);\n        cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);\n\n        if (is_pre)\n            this->BranchToModulePre(module_dest);\n        else\n            this->BranchToModule(module_dest);\n    }\n"""
patcher = replace_once(patcher, "v33-after-x16-block", old_block, new_block)

hdr = replace_once(hdr, "v33-header-symbol", "WindowsNceV32AfterUnlockReturn",
                   "WindowsNceV33AfterX16Return")
hdr = hdr.replace(
    "V32 diagnostic-only target reached from the selected generated post-SVC trampoline after its\n// real UnlockContext sequence has completed. x17 still carries GuestContext here.",
    "V33 diagnostic-only target reached from the selected generated post-SVC trampoline after its\n// real UnlockContext sequence and guest-x16 reload have completed. x17 still carries GuestContext here.",
)

asm = replace_once(asm, "v33-asm-export", "EXPORT  WindowsNceV32AfterUnlockReturn",
                   "EXPORT  WindowsNceV33AfterX16Return")
asm = replace_once(asm, "v33-asm-proc", "WindowsNceV32AfterUnlockReturn PROC",
                   "WindowsNceV33AfterX16Return PROC")
asm = asm.replace(
    "; V32 diagnostic-only controlled return after the selected generated trampoline completed\n; UnlockContext. x17 is still the GuestContext pointer because guest x17 has not been restored yet.",
    "; V33 diagnostic-only controlled return after the selected generated trampoline completed\n; UnlockContext and guest-x16 reload. x17 is still GuestContext because guest x17 is not restored yet.",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
patcher_path.write_text(patcher, encoding="utf-8", newline="\n")
hdr_path.write_text(hdr, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

for path, markers in [
    (cpp_path, ["eden_nce_v33_after_x16.log", "V33_PROBE_ENTER", "V33_AFTER_X16_RETURNED",
                "WindowsNceV33TargetPcAllocationOffset"]),
    (patcher_path, ["module_dest == 0x1F03764", "WindowsNceV33AfterX16Return",
                    "cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);"]),
    (hdr_path, ["WindowsNceV33AfterX16Return"]),
    (asm_path, ["EXPORT  WindowsNceV33AfterX16Return", "WindowsNceV33AfterX16Return PROC"]),
]:
    updated = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in updated:
            raise SystemExit(f"missing V33 marker in {path}: {marker}")

for old_marker in ["V32_PROBE_ENTER", "V32_AFTER_UNLOCK_RETURNED", "WindowsNceV32AfterUnlockReturn"]:
    for path in (cpp_path, patcher_path, hdr_path, asm_path):
        if old_marker in path.read_text(encoding="utf-8"):
            raise SystemExit(f"stale V32 marker in {path}: {old_marker}")

print("REALGAME_V33_AFTER_X16_RETURN=PASS")
