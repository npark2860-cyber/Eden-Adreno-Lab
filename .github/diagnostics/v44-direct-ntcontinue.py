#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v44-direct-ntcontinue.py <arm_nce_windows.cpp>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def replace_once(label: str, old: str, new: str) -> None:
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {n}")
    s = s.replace(old, new, 1)

replace_once(
    "log-file",
    'constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v43_host_bridge_entry.log";',
    'constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v44_direct_ntcontinue.log";',
)

replace_once(
    "selected-direct-ntcontinue",
    """                context.Pc = reinterpret_cast<u64>(&WindowsNceV43ProbeBridge);
                WriteWindowsNceV43Repair(
                    context, *guest, before_x18, live_teb, redirected,
                    params->lock.load(std::memory_order_relaxed));
            }
            return EXCEPTION_CONTINUE_EXECUTION;
""",
    """                context.Pc = reinterpret_cast<u64>(&WindowsNceV43ProbeBridge);
                WriteWindowsNceV43Repair(
                    context, *guest, before_x18, live_teb, redirected,
                    params->lock.load(std::memory_order_relaxed));
                WriteWindowsNceV43Line("V44_DIRECT_NTCONTINUE");
                NCE::WindowsNceTransition::ContinueContext(context);
            }
            return EXCEPTION_CONTINUE_EXECUTION;
""",
)

p.write_text(s, encoding="utf-8", newline="\n")
updated = p.read_text(encoding="utf-8")
for marker in [
    "V44_DIRECT_NTCONTINUE",
    "WindowsNceTransition::ContinueContext(context)",
    "WindowsNceV43ProbeBridge",
    "V43_BRIDGE_ENTRY",
    "eden_nce_v44_direct_ntcontinue.log",
]:
    if marker not in updated:
        raise SystemExit(f"missing V44 marker: {marker}")
print("REALGAME_V44_DIRECT_NTCONTINUE=PASS")
