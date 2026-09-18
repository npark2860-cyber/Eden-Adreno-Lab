#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v46-direct-resume-both-seams.py <arm_nce_windows.cpp>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def replace_once(label: str, old: str, new: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    s = s.replace(old, new, 1)

replace_once(
    "probe-log-name",
    'constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v45_standard_breakpoint.log";',
    'constexpr char WindowsNceV43ProbeFileName[] = "eden_nce_v46_direct_resume.log";',
)

replace_once(
    "probe-bridge-direct-resume",
    """            g_windows_nce_v43_bridge_entry_seen = true;
            context.Pc += sizeof(u32);
            return EXCEPTION_CONTINUE_EXECUTION;
""",
    """            g_windows_nce_v43_bridge_entry_seen = true;
            context.Pc += sizeof(u32);
            WriteWindowsNceV43Line("V46_BRIDGE_NTCONTINUE");
            NCE::WindowsNceTransition::ContinueContext(context);
""",
)

replace_once(
    "selected-redirect-direct-resume",
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
                WriteWindowsNceV43Line("V46_REDIRECT_NTCONTINUE");
                NCE::WindowsNceTransition::ContinueContext(context);
            }
            return EXCEPTION_CONTINUE_EXECUTION;
""",
)

p.write_text(s, encoding="utf-8", newline="\n")
updated = p.read_text(encoding="utf-8")
for marker in [
    "V46_REDIRECT_NTCONTINUE",
    "V46_BRIDGE_NTCONTINUE",
    "WindowsNceTransition::ContinueContext(context)",
    "eden_nce_v46_direct_resume.log",
    "V43_BRIDGE_ENTRY",
]:
    if marker not in updated:
        raise SystemExit(f"missing V46 marker: {marker}")
if updated.count("WindowsNceTransition::ContinueContext(context)") < 2:
    raise SystemExit("expected direct NtContinue at both V46 resume seams")
print("REALGAME_V46_DIRECT_RESUME_BOTH_SEAMS=PASS")
