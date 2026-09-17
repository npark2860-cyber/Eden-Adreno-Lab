#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v27-transition-stack-top.py <windows_nce_transition.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

old = "if (guest->sp <= allocation_base || guest->sp >= allocation_end) {"
new = "if (guest->sp <= allocation_base || guest->sp > allocation_end) {"

count = text.count(old)
if count != 1:
    raise SystemExit(f"transition-stack-top-boundary: expected exactly one source match, found {count}")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8", newline="\n")

updated = path.read_text(encoding="utf-8")
if "guest->sp <= allocation_base || guest->sp > allocation_end" not in updated:
    raise SystemExit("V27 corrected transition upper-bound check missing")
if "guest->sp <= allocation_base || guest->sp >= allocation_end" in updated:
    raise SystemExit("V27 old rejecting transition upper-bound check still present")

print("REALGAME_V27_TRANSITION_STACK_TOP=PASS")
