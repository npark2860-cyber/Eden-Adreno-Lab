#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v23-haltreason.py <physical_core.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


text = replace_once(
    text,
    "logging-include",
    '#include "common/scope_exit.h"\n#include "common/settings.h"\n',
    '#include "common/logging.h"\n#include "common/scope_exit.h"\n#include "common/settings.h"\n',
)

text = replace_once(
    text,
    "halt-reason-classifier",
    "        if (breakpoint || prefetch_abort) {\n",
    "        if (breakpoint || prefetch_abort) {\n"
    "            LOG_ERROR(Core_ARM,\n"
    "                      \"NCE_V23_PHYSICAL_STOP hr=0x{:016X} breakpoint={} prefetch_abort={} step_completed={}\",\n"
    "                      static_cast<u64>(hr), breakpoint, prefetch_abort, step_completed);\n",
)

path.write_text(text, encoding="utf-8", newline="\n")

if "NCE_V23_PHYSICAL_STOP" not in path.read_text(encoding="utf-8"):
    raise SystemExit("V23 marker missing")

print("REALGAME_V23_HALTREASON=PASS")
