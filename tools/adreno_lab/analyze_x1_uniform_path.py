#!/usr/bin/env python3
"""Summarize [X1-UNIFORM-PATH] aggregate lines from an Eden diagnostic log."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

MARKER = "[X1-UNIFORM-PATH]"
PAIR = re.compile(r"([A-Za-z][A-Za-z0-9]*)=([0-9]+)")
FIELDS = (
    "frames", "visits", "bytes", "fast", "fastBytes", "fastAlignment", "fastSkip",
    "cached", "cachedBytes", "cachedClean", "cachedUpload", "skipPolicyVisits",
    "fastUniqueKeys", "fastRepeatKey", "fastSameFrame", "fastSameDraw",
    "fastConsecutiveFrame", "tableOverflow",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    args = ap.parse_args()

    totals = {name: 0 for name in FIELDS}
    windows = 0
    first_frame = None
    last_frame = None
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        if MARKER not in line:
            continue
        values = {k: int(v) for k, v in PAIR.findall(line)}
        if "frame" in values:
            first_frame = values["frame"] if first_frame is None else first_frame
            last_frame = values["frame"]
        for name in FIELDS:
            totals[name] += values.get(name, 0)
        windows += 1

    if windows == 0:
        raise SystemExit("no [X1-UNIFORM-PATH] lines found")

    visits = totals["visits"]
    fast = totals["fast"]
    cached = totals["cached"]
    repeat = totals["fastRepeatKey"]
    print(f"windows={windows} frameRange={first_frame}..{last_frame}")
    for name in FIELDS:
        print(f"{name}={totals[name]}")
    if visits:
        print(f"fastPct={100.0 * fast / visits:.2f}")
        print(f"cachedPct={100.0 * cached / visits:.2f}")
    if fast:
        print(f"fastRepeatKeyPct={100.0 * repeat / fast:.2f}")
        print(f"fastSameFramePct={100.0 * totals['fastSameFrame'] / fast:.2f}")
    if cached:
        print(f"cachedCleanPct={100.0 * totals['cachedClean'] / cached:.2f}")
        print(f"cachedUploadPct={100.0 * totals['cachedUpload'] / cached:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
