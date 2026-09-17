#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: v43r-gate-host-bridge-probe.py <arm_nce_windows.cpp> <windows_nce_entry.asm>")

cpp_path = Path(sys.argv[1])
asm_path = Path(sys.argv[2])
cpp = cpp_path.read_text(encoding="utf-8")
asm = asm_path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# V43 inserted the probe BRK directly at WindowsNceHostStackBridge, which affects every
# host return before the selected seq2 probe is armed. Remove that global mutation first.
asm = replace_once(
    asm,
    "remove-global-bridge-brk",
    """WindowsNceHostStackBridge PROC\n        brk     #61507\n        str     x1, [x18, #8]\n""",
    """WindowsNceHostStackBridge PROC\n        str     x1, [x18, #8]\n""",
)

# Export a separate diagnostic-only bridge that traps once, then tail-branches into the
# untouched production HostStackBridge. Only the selected redirect will point at this symbol.
asm = replace_once(
    asm,
    "export-probe-bridge",
    "        EXPORT  WindowsNceHostStackBridge\n",
    "        EXPORT  WindowsNceHostStackBridge\n        EXPORT  WindowsNceV43ProbeBridge\n",
)
asm = replace_once(
    asm,
    "insert-probe-bridge",
    """WindowsNceHostStackBridge PROC\n        str     x1, [x18, #8]\n""",
    """WindowsNceV43ProbeBridge PROC\n        brk     #61507\n        b       WindowsNceHostStackBridge\n        ENDP\n\nWindowsNceHostStackBridge PROC\n        str     x1, [x18, #8]\n""",
)

cpp = replace_once(
    cpp,
    "declare-probe-bridge",
    "namespace Core {\n\nnamespace {\n",
    "namespace Core {\n\nextern \"C\" void WindowsNceV43ProbeBridge() noexcept;\n\nnamespace {\n",
)

# V43 already restricts this block to the selected target. Redirect only that confirmed
# x18 fallback return to the diagnostic bridge instead of globally modifying HostStackBridge.
cpp = replace_once(
    cpp,
    "gate-selected-redirect",
    """                context.X[18] = live_teb;\n                g_windows_nce_v43_repair_seen = true;\n                WriteWindowsNceV43Repair(\n""",
    """                context.X[18] = live_teb;\n                g_windows_nce_v43_repair_seen = true;\n                context.Pc = reinterpret_cast<u64>(&WindowsNceV43ProbeBridge);\n                WriteWindowsNceV43Repair(\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")
asm_path.write_text(asm, encoding="utf-8", newline="\n")

updated_cpp = cpp_path.read_text(encoding="utf-8")
updated_asm = asm_path.read_text(encoding="utf-8")
for marker in [
    "WindowsNceV43ProbeBridge",
    "context.Pc = reinterpret_cast<u64>(&WindowsNceV43ProbeBridge)",
    "V43_BRIDGE_ENTRY",
    "V43_X18_REPAIR",
]:
    if marker not in updated_cpp:
        raise SystemExit(f"missing V43R cpp marker: {marker}")
for marker in [
    "EXPORT  WindowsNceV43ProbeBridge",
    "WindowsNceV43ProbeBridge PROC",
    "brk     #61507",
    "b       WindowsNceHostStackBridge",
    "WindowsNceHostStackBridge PROC\n        str     x1, [x18, #8]",
]:
    if marker not in updated_asm:
        raise SystemExit(f"missing V43R asm marker: {marker}")
if "WindowsNceHostStackBridge PROC\n        brk     #61507" in updated_asm:
    raise SystemExit("global HostStackBridge BRK still present")

print("REALGAME_V43R_GATED_HOST_BRIDGE_PROBE=PASS")
