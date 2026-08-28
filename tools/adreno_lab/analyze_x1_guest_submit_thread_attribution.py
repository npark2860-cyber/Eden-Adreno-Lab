#!/usr/bin/env python3
"""Summarize [X1-GUESTSUBMIT] and align it with GPU submit/command attribution."""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

KV_RE = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")


def parse_value(raw: str):
    raw = raw.rstrip(",")
    if raw.endswith("ms"):
        return float(raw[:-2])
    if raw.endswith("%"):
        return float(raw[:-1])
    try:
        return int(raw, 0)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def parse_records(text: str, marker: str):
    records = []
    for line in text.splitlines():
        if marker not in line:
            continue
        fields = {key: parse_value(value) for key, value in KV_RE.findall(line)}
        if "frame" in fields:
            records.append(fields)
    return records


def median(values):
    return statistics.median(values) if values else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    args = ap.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    guest = parse_records(text, "[X1-GUESTSUBMIT]")
    submit = {int(r["frame"]): r for r in parse_records(text, "[X1-GPUSUBMIT]")}
    gpucmd = {int(r["frame"]): r for r in parse_records(text, "[X1-GPUCMD]")}
    if not guest:
        raise SystemExit("No [X1-GUESTSUBMIT] records found")

    print(f"records={len(guest)}")
    print("frame wall/f threads tid dom% gapAvg cpuShare submitGap qwait/f active/f pc")
    print("----- ------ ------- --- ---- ------- -------- --------- ------- -------- --")

    cpu_shares = []
    dom_shares = []
    gap_avgs = []
    submit_gap_avgs = []
    qwait_pfs = []
    active_pfs = []
    tids = []

    for g in guest:
        frame = int(g["frame"])
        frames = int(g.get("frames", 120)) or 120
        wall_pf = float(g.get("wall", 0.0)) / frames
        gap_n = int(g.get("gapN", 0))
        gap_avg = float(g.get("wallGap", 0.0)) / gap_n if gap_n else 0.0
        cpu_share = float(g.get("cpuShare", 0.0))
        dom_share = float(g.get("domShare", 0.0))
        tid = int(g.get("tid", 0))
        pc = int(g.get("pc", 0))

        s = submit.get(frame, {})
        submit_gap_n = int(s.get("serviceGapN", 0))
        submit_gap = float(s.get("serviceGap", 0.0)) / submit_gap_n if submit_gap_n else 0.0

        c = gpucmd.get(frame, {})
        qwait_pf = float(c.get("queueWait", 0.0)) / frames
        active_pf = float(c.get("active", 0.0)) / frames

        print(f"{frame:5d} {wall_pf:6.2f} {int(g.get('threads', 0)):7d} {tid:#x} "
              f"{dom_share:5.1f} {gap_avg:7.2f} {cpu_share:8.2f} {submit_gap:9.2f} "
              f"{qwait_pf:7.2f} {active_pf:8.2f} {pc:#x}")

        cpu_shares.append(cpu_share)
        dom_shares.append(dom_share)
        gap_avgs.append(gap_avg)
        if submit_gap_n:
            submit_gap_avgs.append(submit_gap)
        if c:
            qwait_pfs.append(qwait_pf)
            active_pfs.append(active_pf)
        if tid:
            tids.append(tid)

    print("\nmedians across report windows")
    print(f"  dominant submitter share : {median(dom_shares):.2f}%")
    print(f"  dominant wall gap avg    : {median(gap_avgs):.3f} ms")
    print(f"  submitter guest CPU share: {median(cpu_shares):.2f}%")
    if submit_gap_avgs:
        print(f"  NVDRV submit gap avg     : {median(submit_gap_avgs):.3f} ms")
    if qwait_pfs:
        print(f"  GPU queueWait/frame      : {median(qwait_pfs):.3f} ms")
        print(f"  GPU active/frame         : {median(active_pfs):.3f} ms")

    unique_tids = sorted(set(tids))
    print(f"  dominant thread ids      : {', '.join(hex(t) for t in unique_tids) if unique_tids else 'none'}")

    print("\ninterpretation guide")
    print("  high dominant share + high cpuShare => one guest submitter is CPU-bound between submissions")
    print("  high dominant share + low cpuShare  => submitter spends most guest time waiting/preempted; trace kernel wait/SVC causes next")
    print("  low dominant share / many tids      => GPU production is distributed across guest threads; attribute per-thread before deeper tracing")
    print("  stable caller pc is identity evidence only; it does not prove work between submissions executes at that pc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
