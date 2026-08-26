#!/usr/bin/env python3
"""Summarize [X1-FLOW][BUFFER] Draw/Dispatch resource-category telemetry."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re

ROW_RE = re.compile(
    r"\[X1-FLOW\]\[BUFFER\].*?frame=(?P<frame>\d+)\s+frames=(?P<frames>\d+)\s+"
    r"kind=(?P<kind>\S+)\s+cat=(?P<cat>\S+)\s+scopes=(?P<scopes>\d+)\s+"
    r"uploadReq=(?P<upload_req>\d+)\s+upload=(?P<upload>[0-9.]+)MiB\s+"
    r"copy=(?P<copy_calls>\d+)\s+(?P<copy>[0-9.]+)MiB\s+outside=(?P<outside>\d+)\s+"
    r"barriers=(?P<barriers>\d+)\s+wait=(?P<wait>[0-9.]+)ms"
)

FIELDS = ("scopes", "upload_req", "upload", "copy_calls", "copy", "outside", "barriers", "wait")


def parse(path: Path):
    totals = defaultdict(lambda: defaultdict(float))
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ROW_RE.search(line)
        if not m:
            continue
        d = m.groupdict()
        key = (d["kind"], d["cat"])
        values = {
            "scopes": int(d["scopes"]),
            "upload_req": int(d["upload_req"]),
            "upload": float(d["upload"]),
            "copy_calls": int(d["copy_calls"]),
            "copy": float(d["copy"]),
            "outside": int(d["outside"]),
            "barriers": int(d["barriers"]),
            "wait": float(d["wait"]),
        }
        for name, value in values.items():
            totals[key][name] += value
        rows.append((int(d["frame"]), int(d["frames"]), key, values))
    return totals, rows


def pct(value: float, total: float) -> float:
    return 0.0 if total == 0 else value * 100.0 / total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()

    totals, rows = parse(args.log)
    if not rows:
        print("No [X1-FLOW][BUFFER] rows found.")
        return 2

    print(f"BUFFER rows: {len(rows)}")
    for kind in ("draw", "dispatch"):
        entries = [(cat, vals) for (k, cat), vals in totals.items() if k == kind]
        if not entries:
            continue
        total_upload = sum(v["upload"] for _, v in entries)
        total_copy = sum(v["copy"] for _, v in entries)
        total_outside = sum(v["outside"] for _, v in entries)
        total_barriers = sum(v["barriers"] for _, v in entries)
        print(f"\n[{kind.upper()}] upload={total_upload:.3f} MiB copy={total_copy:.3f} MiB "
              f"outside={int(total_outside)} barriers={int(total_barriers)}")
        entries.sort(key=lambda item: (item[1]["upload"], item[1]["copy"], item[1]["outside"]), reverse=True)
        for cat, v in entries:
            print(
                f"  {cat:20s} scopes={int(v['scopes']):9d} "
                f"uploadReq={int(v['upload_req']):9d} upload={v['upload']:10.3f} MiB "
                f"({pct(v['upload'], total_upload):6.2f}%) "
                f"copy={v['copy']:10.3f} MiB ({pct(v['copy'], total_copy):6.2f}%) "
                f"outside={int(v['outside']):8d} ({pct(v['outside'], total_outside):6.2f}%) "
                f"barriers={int(v['barriers']):8d} ({pct(v['barriers'], total_barriers):6.2f}%) "
                f"wait={v['wait']:.3f} ms"
            )

    print("\nTop 20 reporting-window category spikes by upload:")
    for frame, frames, (kind, cat), v in sorted(rows, key=lambda row: row[3]["upload"], reverse=True)[:20]:
        print(f"  frame={frame:6d} frames={frames:4d} {kind:8s}/{cat:20s} "
              f"upload={v['upload']:9.3f} MiB copy={v['copy']:9.3f} MiB "
              f"outside={v['outside']:6d} barriers={v['barriers']:6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
