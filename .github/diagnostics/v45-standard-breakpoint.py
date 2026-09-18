#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: v45-standard-breakpoint.py <arm_nce_windows.cpp> <windows_nce_entry.asm>")

cpp_path = Path(sys.argv[1])
asm_path = Path(sys.argv[2])
cpp = cpp_path.read_text(encoding="utf-8")
asm = asm_path.read_text(encoding="utf-8")

def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)

cpp = replace_once(
    cpp,
    "probe-log-name",
    'constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v43_host_bridge_entry.log";',
    'constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v45_standard_breakpoint.log";',
)
cpp = replace_once(
    cpp,
    "breakpoint-immediate",
    "constexpr u32 WindowsNceV43BridgeBreakpointImmediate = 0xF043;",
    "constexpr u32 WindowsNceV43BridgeBreakpointImmediate = 0xF000;",
)
cpp = replace_once(
    cpp,
    "breakpoint-static-assert",
    "static_assert(WindowsNceV43BridgeBreakpointInstruction == 0xD43E0860u);",
    "static_assert(WindowsNceV43BridgeBreakpointInstruction == 0xD43E0000u);",
)
asm = replace_once(
    asm,
    "probe-bridge-standard-brk",
    """WindowsNceV43ProbeBridge PROC
        brk     #61507
        b       WindowsNceHostStackBridge
""",
    """WindowsNceV43ProbeBridge PROC
        brk     #61440
        b       WindowsNceHostStackBridge
""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

ucpp = cpp_path.read_text(encoding="utf-8")
uasm = asm_path.read_text(encoding="utf-8")
for marker in [
    "WindowsNceV43BridgeBreakpointImmediate = 0xF000",
    "0xD43E0000u",
    "eden_nce_v45_standard_breakpoint.log",
    "V43_BRIDGE_ENTRY",
]:
    if marker not in ucpp:
        raise SystemExit(f"missing V45 cpp marker: {marker}")
if "WindowsNceV43ProbeBridge PROC\n        brk     #61440" not in uasm:
    raise SystemExit("missing V45 standard Windows ARM64 BRK #0xF000")
if "V44_DIRECT_NTCONTINUE" in ucpp:
    raise SystemExit("V44 direct NtContinue must not be present in V45")
print("REALGAME_V45_STANDARD_BREAKPOINT=PASS")
