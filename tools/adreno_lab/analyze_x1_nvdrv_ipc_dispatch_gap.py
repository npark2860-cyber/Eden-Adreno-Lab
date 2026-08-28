#!/usr/bin/env python3
"""Summarize [X1-IPCDISPATCH] 120-frame reports."""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

LINE_RE = re.compile(r"\[X1-IPCDISPATCH\]\s+(.*)")
KV_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=([^\s]+)")


def parse_num(value: str):
    value = value.rstrip(",")
    if value.endswith("ms"):
        value = value[:-2]
    if value.endswith("%"):
        value = value[:-1]
    if value.startswith("0x"):
        return int(value, 16)
    try:
        if any(c in value for c in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value


def parse(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE_RE.search(line)
        if not m:
            continue
        row = {k: parse_num(v) for k, v in KV_RE.findall(m.group(1))}
        if row:
            rows.append(row)
    return rows


def stat(rows, key):
    vals = [float(r[key]) for r in rows if key in r and isinstance(r[key], (int, float))]
    if not vals:
        return None
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "mean": statistics.fmean(vals),
        "min": min(vals),
        "max": max(vals),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--min-frame", type=int, default=0)
    ap.add_argument("--max-frame", type=int, default=2**63 - 1)
    args = ap.parse_args()

    rows = [
        r for r in parse(args.log)
        if args.min_frame <= int(r.get("frame", 0)) <= args.max_frame
    ]
    if not rows:
        raise SystemExit("no [X1-IPCDISPATCH] rows in selected range")

    print(f"reports={len(rows)} frame={rows[0].get('frame')}..{rows[-1].get('frame')}")
    print("frame tid requests guestPostAvg ipcDispatchAvg serviceReplyAvg guestPostMax ipcDispatchMax serviceReplyMax missingA missingB")
    for r in rows:
        print(
            r.get("frame", "-"), hex(int(r.get("tid", 0))), r.get("requests", "-"),
            r.get("guestPostAvg", "-"), r.get("ipcDispatchAvg", "-"),
            r.get("serviceReplyAvg", "-"), r.get("guestPostMax", "-"),
            r.get("ipcDispatchMax", "-"), r.get("serviceReplyMax", "-"),
            r.get("missingA", "-"), r.get("missingB", "-"),
        )

    print("\naggregate:")
    for key in (
        "wall", "requests", "guestPostAvg", "ipcDispatchAvg", "serviceReplyAvg",
        "guestPostMax", "ipcDispatchMax", "serviceReplyMax", "missingA", "missingB",
    ):
        s = stat(rows, key)
        if s:
            print(
                f"{key}: n={s['n']} median={s['median']:.6f} "
                f"mean={s['mean']:.6f} min={s['min']:.6f} max={s['max']:.6f}"
            )

    guest = stat(rows, "guestPostAvg")
    dispatch = stat(rows, "ipcDispatchAvg")
    service = stat(rows, "serviceReplyAvg")
    if guest and dispatch and service:
        print("\ninterpretation:")
        gm, dm, sm = guest["median"], dispatch["median"], service["median"]
        if gm > dm * 3 and gm > sm * 3:
            print("guestPostReply dominates: guest-side post-reply work/wait is the primary gap.")
        elif dm > gm * 3 and dm > sm * 3:
            print("ipcDispatch dominates: request is issued promptly but nvservices dispatch/wakeup is late.")
        elif sm > gm * 3 and sm > dm * 3:
            print("serviceReply dominates: NVDRV handler/reply body is unexpectedly owning the gap.")
        else:
            print("multiple components are material; inspect per-window values before attribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
