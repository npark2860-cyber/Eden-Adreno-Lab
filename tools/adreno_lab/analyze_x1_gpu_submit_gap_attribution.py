#!/usr/bin/env python3
"""Summarize [X1-GPUSUBMIT] and align it with [X1-GPUCMD] 120-frame records."""

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


def ratio_ms(total, count):
    return float(total) / float(count) if count else 0.0


def median(values):
    return statistics.median(values) if values else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    args = ap.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    submit = parse_records(text, "[X1-GPUSUBMIT]")
    gpucmd = {int(r["frame"]): r for r in parse_records(text, "[X1-GPUCMD]")}
    if not submit:
        raise SystemExit("No [X1-GPUSUBMIT] records found")

    print(f"records={len(submit)}")
    print("frame  wall/f  qwait/f active/f svcGapAvg devGapAvg pushGapAvg svc/f impl/f lock/f copy/f")
    print("-----  ------  ------- -------- --------- --------- ---------- ----- ------ ------ ------")

    service_gap_avgs = []
    device_gap_avgs = []
    push_gap_avgs = []
    service_per_frames = []
    impl_per_frames = []
    lock_per_frames = []
    copy_per_frames = []
    queue_wait_per_frames = []
    active_per_frames = []

    for s in submit:
        frame = int(s["frame"])
        frames = int(s.get("frames", 120)) or 120
        wall_pf = float(s.get("wall", 0.0)) / frames
        svc_gap_avg = ratio_ms(s.get("serviceGap", 0.0), s.get("serviceGapN", 0))
        dev_gap_avg = ratio_ms(s.get("deviceGap", 0.0), s.get("deviceGapN", 0))
        push_gap_avg = ratio_ms(s.get("pushGap", 0.0), s.get("pushGapN", 0))
        svc_pf = float(s.get("serviceTime", 0.0)) / frames
        impl_pf = float(s.get("implTime", 0.0)) / frames
        lock_pf = float(s.get("lockWait", 0.0)) / frames
        copy_pf = float(s.get("copy", 0.0)) / frames

        g = gpucmd.get(frame, {})
        qwait_pf = float(g.get("queueWait", 0.0)) / frames
        active_pf = float(g.get("active", 0.0)) / frames

        print(f"{frame:5d}  {wall_pf:6.2f}  {qwait_pf:7.2f} {active_pf:8.2f} "
              f"{svc_gap_avg:9.2f} {dev_gap_avg:9.2f} {push_gap_avg:10.2f} "
              f"{svc_pf:5.2f} {impl_pf:6.2f} {lock_pf:6.2f} {copy_pf:6.2f}")

        service_gap_avgs.append(svc_gap_avg)
        device_gap_avgs.append(dev_gap_avg)
        push_gap_avgs.append(push_gap_avg)
        service_per_frames.append(svc_pf)
        impl_per_frames.append(impl_pf)
        lock_per_frames.append(lock_pf)
        copy_per_frames.append(copy_pf)
        if g:
            queue_wait_per_frames.append(qwait_pf)
            active_per_frames.append(active_pf)

    print("\nmedians across report windows")
    print(f"  service-entry gap avg : {median(service_gap_avgs):.3f} ms")
    print(f"  nvhost-device gap avg : {median(device_gap_avgs):.3f} ms")
    print(f"  PushGPUEntries gap avg: {median(push_gap_avgs):.3f} ms")
    print(f"  service work/frame    : {median(service_per_frames):.3f} ms")
    print(f"  SubmitGPFIFOImpl/frame: {median(impl_per_frames):.3f} ms")
    print(f"  channel lock/frame    : {median(lock_per_frames):.3f} ms")
    print(f"  command copy/frame    : {median(copy_per_frames):.3f} ms")
    if queue_wait_per_frames:
        print(f"  GPU queueWait/frame   : {median(queue_wait_per_frames):.3f} ms")
        print(f"  GPU active/frame      : {median(active_per_frames):.3f} ms")

    total_service = sum(int(s.get("service", 0)) for s in submit)
    total_device = sum(int(s.get("device", 0)) for s in submit)
    total_main_push = sum(int(s.get("mainPush", 0)) for s in submit)
    total_push = sum(int(s.get("pushEntries", 0)) for s in submit)
    print("\ncounts")
    print(f"  service candidates={total_service} device GPU submits={total_device} "
          f"main pushes={total_main_push} all submit pushes={total_push}")
    if total_service != total_device:
        print("  NOTE: service candidate count differs from device GPU-submit count; "
              "prefer device/push gap for attribution.")

    print("\ninterpretation guide")
    print("  large service/device/push gaps + tiny service/impl/lock/copy => upstream guest CPU/submission producer gap")
    print("  small service-entry gap but large serviceTime/read/dispatch => NVDRV IPC/HLE service path")
    print("  large impl/lock/copy => nvhost_gpu GPFIFO preparation/serialization path")
    print("  push gaps track GPU queueWait while push-call time stays tiny => GPU worker starvation is supplied from upstream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
