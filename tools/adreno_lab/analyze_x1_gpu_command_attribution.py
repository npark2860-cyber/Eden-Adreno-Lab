#!/usr/bin/env python3
"""Summarize [X1-GPUCMD] 120-frame aggregates from an Eden runtime log."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from statistics import median

LINE = re.compile(r"\[X1-GPUCMD\]\s+(.*)$")
PAIR = re.compile(r"([A-Za-z][A-Za-z0-9]*)=([0-9]+(?:\.[0-9]+)?)(ms)?")


def parse(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE.search(line)
        if not match:
            continue
        row = {}
        for key, value, unit in PAIR.findall(match.group(1)):
            row[key] = float(value) if unit or "." in value else int(value)
        if row:
            rows.append(row)
    return rows


def per_frame(row, key):
    frames = int(row.get("frames", 0))
    return float(row.get(key, 0.0)) / frames if frames else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--min-frame", type=int, default=0)
    parser.add_argument("--max-frame", type=int, default=2**63 - 1)
    args = parser.parse_args()

    rows = [
        row for row in parse(args.log)
        if args.min_frame <= int(row.get("frame", 0)) <= args.max_frame
    ]
    if not rows:
        raise SystemExit("no [X1-GPUCMD] rows in requested frame range")

    print(f"rows={len(rows)} frameRange={int(rows[0]['frame'])}..{int(rows[-1]['frame'])}")
    time_keys = [
        "wall", "queueWait", "active", "submit", "push", "blockWait",
        "sched", "bind", "dispatch", "dma", "loop", "tail", "syncWait", "process",
    ]
    for key in time_keys:
        values = [per_frame(row, key) for row in rows]
        print(f"{key:>10} ms/frame median={median(values):8.3f} mean={sum(values)/len(values):8.3f}")

    count_keys = [
        "workerPop", "submitCalls", "pushCalls", "blockCalls", "schedCalls",
        "dmaCalls", "steps", "syncWaitCalls", "processCalls", "words",
        "callMethod", "callMulti", "multiMethods",
    ]
    for key in count_keys:
        values = [per_frame(row, key) for row in rows]
        print(f"{key:>10} /frame   median={median(values):8.2f} mean={sum(values)/len(values):8.2f}")

    print("\nInterpretation:")
    print("- queueWait high => the asynchronous GPU worker is often idle waiting for upstream commands.")
    print("- active/dma/process high => Eden command processing is consuming the frame budget.")
    print("- push blockWait high => an upstream caller is synchronously waiting for the GPU worker.")
    print("- Timings are nested and asynchronous; do not add them as mutually exclusive frame slices.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
