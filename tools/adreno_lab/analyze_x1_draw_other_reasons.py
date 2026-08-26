#!/usr/bin/env python3
"Summarize Draw other/* reason buckets from [X1-FLOW][BUFFER] telemetry."

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


def pct(value: float, total: float) -> float:
    return 0.0 if total == 0 else value * 100.0 / total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()

    totals = defaultdict(lambda: defaultdict(float))
    rows = []
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ROW_RE.search(line)
        if not m or m.group("kind") != "draw":
            continue
        cat = m.group("cat")
        if cat != "other" and not cat.startswith("other/"):
            continue
        values = {
            "scopes": int(m.group("scopes")),
            "upload_req": int(m.group("upload_req")),
            "upload": float(m.group("upload")),
            "copy_calls": int(m.group("copy_calls")),
            "copy": float(m.group("copy")),
            "outside": int(m.group("outside")),
            "barriers": int(m.group("barriers")),
            "wait": float(m.group("wait")),
        }
        for key, value in values.items():
            totals[cat][key] += value
        rows.append((int(m.group("frame")), int(m.group("frames")), cat, values))

    if not rows:
        print("No Draw other/ reason rows found.")
        return 2

    total_upload = sum(v["upload"] for v in totals.values())
    total_copy = sum(v["copy"] for v in totals.values())
    total_outside = sum(v["outside"] for v in totals.values())
    total_barriers = sum(v["barriers"] for v in totals.values())
    total_wait = sum(v["wait"] for v in totals.values())

    print(
        f"Draw other-family: upload={total_upload:.3f} MiB copy={total_copy:.3f} MiB "
        f"outside={int(total_outside)} barriers={int(total_barriers)} wait={total_wait:.3f} ms"
    )
    ordered = sorted(
        totals.items(),
        key=lambda item: (item[1]["outside"], item[1]["barriers"], item[1]["upload"], item[1]["copy"]),
        reverse=True,
    )
    for cat, v in ordered:
        print(
            f"  {cat:34s} scopes={int(v['scopes']):9d} "
            f"uploadReq={int(v['upload_req']):9d} upload={v['upload']:10.3f} MiB "
            f"({pct(v['upload'], total_upload):6.2f}%) "
            f"copy={v['copy']:10.3f} MiB ({pct(v['copy'], total_copy):6.2f}%) "
            f"outside={int(v['outside']):8d} ({pct(v['outside'], total_outside):6.2f}%) "
            f"barriers={int(v['barriers']):8d} ({pct(v['barriers'], total_barriers):6.2f}%) "
            f"wait={v['wait']:.3f} ms"
        )

    print("\nTop 20 other-family reporting-window spikes by outside-RP:")
    for frame, frames, cat, v in sorted(
        rows, key=lambda row: (row[3]["outside"], row[3]["barriers"], row[3]["upload"]), reverse=True
    )[:20]:
        print(
            f"  frame={frame:6d} frames={frames:4d} {cat:34s} "
            f"upload={v['upload']:9.3f} MiB copy={v['copy']:9.3f} MiB "
            f"outside={v['outside']:6d} barriers={v['barriers']:6d} wait={v['wait']:.3f} ms"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
