#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v26-teb-stack-top.py <arm_nce_windows.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

old = """    if (guest_sp_value <= allocation_base || guest_sp_value >= allocation_end) {\n        return false;\n    }\n"""
new = """    // A downward-growing stack may begin with SP exactly at StackBase, which is one-past\n    // the highest address in the allocation. VirtualQuery above intentionally probes SP - 1,\n    // so accept guest_sp == allocation_end while still rejecting values above the allocation.\n    if (guest_sp_value <= allocation_base || guest_sp_value > allocation_end) {\n        return false;\n    }\n"""

count = text.count(old)
if count != 1:
    raise SystemExit(f"teb-stack-top-boundary: expected exactly one source match, found {count}")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8", newline="\n")

updated = path.read_text(encoding="utf-8")
if "guest_sp_value > allocation_end" not in updated:
    raise SystemExit("V26 corrected upper-bound check missing")
if "guest_sp_value >= allocation_end" in updated:
    raise SystemExit("V26 old rejecting upper-bound check still present")

print("REALGAME_V26_TEB_STACK_TOP=PASS")
