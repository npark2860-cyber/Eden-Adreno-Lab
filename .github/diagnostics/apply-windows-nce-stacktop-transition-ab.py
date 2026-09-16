from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

old = "if (guest->sp <= allocation_base || guest->sp >= allocation_end) {"
new = "if (guest->sp <= allocation_base || guest->sp > allocation_end) {"

count = text.count(old)
if count != 1:
    raise SystemExit(f"stacktop-transition-ab: expected exactly one source match, found {count}")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8", newline="\n")
print("REALGAME_STACKTOP_TRANSITION_AB=PASS")
