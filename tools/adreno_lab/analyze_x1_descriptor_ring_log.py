#!/usr/bin/env python3
"""Aggregate [X1-DBUF] reports emitted by the dc95 descriptor-ring profiler."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

REPORT = re.compile(
    r"\[X1-DBUF\]\s+frames=(?P<frames>\d+)\s+\|\s+"
    r"alloc=(?P<alloc>\d+)\s+bytes=(?P<bytes>\d+)\s+\([^)]*\)\s+\|\s+"
    r"reuseWait=(?P<reuse_count>\d+)\s+(?P<reuse_ms>[0-9.]+)ms\s+\|\s+"
    r"chunkSwitch=(?P<switch_count>\d+)\s+\([^)]*\)\s+\|\s+"
    r"exhaustionFinish=(?P<finish_count>\d+)\s+(?P<finish_ms>[0-9.]+)ms"
)


@dataclass
class Totals:
    reports: int = 0
    frames: int = 0
    alloc: int = 0
    bytes: int = 0
    reuse_count: int = 0
    reuse_ms: float = 0.0
    switch_count: int = 0
    finish_count: int = 0
    finish_ms: float = 0.0

    def add(self, m: re.Match[str]) -> None:
        self.reports += 1
        self.frames += int(m["frames"])
        self.alloc += int(m["alloc"])
        self.bytes += int(m["bytes"])
        self.reuse_count += int(m["reuse_count"])
        self.reuse_ms += float(m["reuse_ms"])
        self.switch_count += int(m["switch_count"])
        self.finish_count += int(m["finish_count"])
        self.finish_ms += float(m["finish_ms"])


def per(value: float, denominator: int) -> float:
    return value / denominator if denominator else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    args = ap.parse_args()

    totals = Totals()
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = REPORT.search(line)
        if match:
            totals.add(match)

    if totals.reports == 0:
        raise SystemExit("No [X1-DBUF] report lines found")

    print(f"reports={totals.reports}")
    print(f"frames={totals.frames}")
    print(f"allocations={totals.alloc} ({per(totals.alloc, totals.frames):.2f}/frame)")
    print(f"descriptor_bytes={totals.bytes} ({per(totals.bytes / 1024.0, totals.frames):.2f} KiB/frame)")
    print(
        f"reuse_wait={totals.reuse_count} total={totals.reuse_ms:.3f} ms "
        f"({per(totals.reuse_ms, totals.frames):.4f} ms/frame)"
    )
    print(f"chunk_switches={totals.switch_count} ({per(totals.switch_count, totals.frames):.4f}/frame)")
    print(
        f"exhaustion_finish={totals.finish_count} total={totals.finish_ms:.3f} ms "
        f"({per(totals.finish_ms, totals.frames):.4f} ms/frame)"
    )

    if totals.finish_count > 0:
        verdict = "OPEN_STRONG: descriptor-frame exhaustion caused forced Scheduler::Finish"
    elif totals.reuse_ms > 0.1 * totals.frames:
        verdict = "OPEN: material frame-slot reuse wait; correlate with scheduler/GPU progress"
    else:
        verdict = "LOW_FOR_SCENE: no exhaustion and reuse-wait cost is small"
    print(f"verdict={verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
