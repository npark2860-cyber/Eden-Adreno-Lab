#!/usr/bin/env python3
"""Summarize [X1-GUESTWAIT] 120-frame reports from an Eden log."""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

LINE = re.compile(
    r"\[X1-GUESTWAIT\].*?frame=(?P<frame>\d+).*?wall=(?P<wall>[0-9.]+)ms.*?"
    r"tid=(?P<tid>0x[0-9a-fA-F]+).*?windows=(?P<windows>\d+).*?"
    r"window=(?P<window>[0-9.]+)ms.*?windowAvg=(?P<window_avg>[0-9.]+)ms.*?"
    r"wait=(?P<wait>[0-9.]+)ms.*?waitShare=(?P<share>[0-9.]+)%.*?"
    r"residual=(?P<residual>[0-9.]+)ms.*?none=(?P<none>[0-9.]+)ms.*?"
    r"sleep=(?P<sleep>[0-9.]+)ms.*?ipc=(?P<ipc>[0-9.]+)ms.*?"
    r"sync=(?P<sync>[0-9.]+)ms.*?cond=(?P<cond>[0-9.]+)ms.*?"
    r"arb=(?P<arb>[0-9.]+)ms.*?susp=(?P<susp>[0-9.]+)ms"
)

FIELDS = (
    "wall",
    "window",
    "window_avg",
    "wait",
    "share",
    "residual",
    "none",
    "sleep",
    "ipc",
    "sync",
    "cond",
    "arb",
    "susp",
)


def parse(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE.search(line)
        if not match:
            continue
        row = {
            "frame": int(match.group("frame")),
            "tid": match.group("tid"),
            "windows": int(match.group("windows")),
        }
        for field in FIELDS:
            row[field] = float(match.group(field))
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--min-frame", type=int, default=0)
    args = parser.parse_args()

    rows = [row for row in parse(args.log) if row["frame"] >= args.min_frame]
    if not rows:
        raise SystemExit("no [X1-GUESTWAIT] rows matched")

    print(f"rows={len(rows)} frames={rows[0]['frame']}..{rows[-1]['frame']}")
    tids = {}
    for row in rows:
        tids[row["tid"]] = tids.get(row["tid"], 0) + row["windows"]
    print(
        "window-weighted tids:",
        ", ".join(
            f"{tid}={count}" for tid, count in sorted(tids.items(), key=lambda kv: kv[1], reverse=True)
        ),
    )

    for field in FIELDS:
        values = [row[field] for row in rows]
        print(
            f"{field:>10}: median={statistics.median(values):9.3f} "
            f"mean={statistics.fmean(values):9.3f} min={min(values):9.3f} max={max(values):9.3f}"
        )

    reason_names = ("none", "sleep", "ipc", "sync", "cond", "arb", "susp")
    reason_totals = {name: sum(row[name] for row in rows) for name in reason_names}
    total_wait = sum(reason_totals.values())
    print("reason totals:")
    for name, value in sorted(reason_totals.items(), key=lambda kv: kv[1], reverse=True):
        share = 0.0 if total_wait == 0 else value * 100.0 / total_wait
        print(f"  {name:>5}: {value:10.3f} ms  {share:6.2f}% of tracked wait")

    print("\nper report:")
    for row in rows:
        dominant_reason = max(reason_names, key=lambda key: row[key])
        print(
            f"frame={row['frame']:5d} tid={row['tid']:>6} windows={row['windows']:4d} "
            f"windowAvg={row['window_avg']:7.3f}ms waitShare={row['share']:6.2f}% "
            f"residual={row['residual']:8.3f}ms dominant={dominant_reason}:{row[dominant_reason]:8.3f}ms"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
