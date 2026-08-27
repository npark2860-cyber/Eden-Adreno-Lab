#!/usr/bin/env python3
'''Analyze [X1-CADENCE] records from an Eden log.

The report separates producer QueueBuffer cadence from compositor acquisition cadence and, when
present, reports raw guest swap interval separately from the compositor effective interval used by
the swap-3-to-2 A/B.
'''

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import statistics
import sys

QUEUE_RE = re.compile(
    r"\[X1-CADENCE\]\[QUEUE\] hostUs=(\d+) core=0x([0-9a-fA-F]+) frame=(\d+) "
    r"slot=(-?\d+) swap=(-?\d+)"
)
ACQUIRE_RE = re.compile(
    r"\[X1-CADENCE\]\[ACQUIRE\] hostUs=(\d+) tick=(\d+) consumer=(-?\d+) "
    r"overlay=(true|false|0|1) frame=(\d+) swap=(-?\d+)(?: effective=(-?\d+))?"
)
VI_RE = re.compile(
    r"\[X1-CADENCE\]\[VI\] hostUs=(\d+) tick=(\d+) mainNew=(\d+) overlayNew=(\d+) "
    r"waitUs=(\d+) workUs=(\d+)"
)


def bucket_ms(delta_us: int) -> str:
    ms = delta_us / 1000.0
    if ms < 25.0:
        return "<25ms (~60fps-or-faster)"
    if ms < 42.0:
        return "25-42ms (~30fps)"
    if ms < 58.0:
        return "42-58ms (~20fps)"
    return ">=58ms"


def summarize_deltas(values: list[int]) -> str:
    if not values:
        return "no intervals"
    ms = [v / 1000.0 for v in values]
    buckets: dict[str, int] = defaultdict(int)
    for value in values:
        buckets[bucket_ms(value)] += 1
    bucket_text = ", ".join(f"{k}={v}" for k, v in buckets.items())
    return (
        f"n={len(values)} avg={statistics.fmean(ms):.3f}ms "
        f"median={statistics.median(ms):.3f}ms min={min(ms):.3f}ms max={max(ms):.3f}ms; "
        f"{bucket_text}"
    )


def consecutive_deltas(values: list[int]) -> list[int]:
    return [b - a for a, b in zip(values, values[1:]) if b >= a]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_frame_cadence.py <eden-log>")

    path = Path(sys.argv[1])
    queue_by_core: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    acquire_by_consumer: dict[int, list[tuple[int, int, int, int, int]]] = defaultdict(list)
    vi: list[tuple[int, int, int, int, int, int]] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if m := QUEUE_RE.search(line):
            host_us, core, frame, _slot, swap = m.groups()
            queue_by_core[core].append((int(host_us), int(frame), int(swap)))
            continue
        if m := ACQUIRE_RE.search(line):
            host_us, tick, consumer, overlay, frame, swap, effective = m.groups()
            if overlay in ("false", "0"):
                raw = int(swap)
                effective_value = raw if effective is None else int(effective)
                acquire_by_consumer[int(consumer)].append(
                    (int(host_us), int(tick), int(frame), raw, effective_value)
                )
            continue
        if m := VI_RE.search(line):
            vi.append(tuple(map(int, m.groups())))

    print(f"log: {path}")
    print(f"VI records: {len(vi)}")
    print(f"producer cores: {len(queue_by_core)}")
    print(f"main consumers: {len(acquire_by_consumer)}")

    if vi:
        host_times = [row[0] for row in vi]
        new_ticks = sum(1 for row in vi if row[2] > 0)
        wait_us = [row[4] for row in vi]
        work_us = [row[5] for row in vi]
        print("\n[VI 60Hz composition thread]")
        print("tick wall cadence:", summarize_deltas(consecutive_deltas(host_times)))
        print(f"ticks with a new main buffer: {new_ticks}/{len(vi)} ({100.0 * new_ticks / len(vi):.2f}%)")
        print(
            f"WaitForComposite avg={statistics.fmean(wait_us)/1000.0:.3f}ms "
            f"median={statistics.median(wait_us)/1000.0:.3f}ms max={max(wait_us)/1000.0:.3f}ms"
        )
        print(
            f"ComposeLocked work avg={statistics.fmean(work_us)/1000.0:.3f}ms "
            f"median={statistics.median(work_us)/1000.0:.3f}ms max={max(work_us)/1000.0:.3f}ms"
        )

    print("\n[Producer QueueBuffer cadence by queue core — raw guest swap]")
    for core, rows in sorted(queue_by_core.items(), key=lambda kv: len(kv[1]), reverse=True):
        times = [row[0] for row in rows]
        swaps = defaultdict(int)
        for _, _, swap in rows:
            swaps[swap] += 1
        print(f"core=0x{core} queues={len(rows)} rawSwaps={dict(swaps)}")
        print("  wall cadence:", summarize_deltas(consecutive_deltas(times)))

    print("\n[Main-buffer acquisition cadence by consumer]")
    for consumer, rows in sorted(acquire_by_consumer.items(), key=lambda kv: len(kv[1]), reverse=True):
        host_times = [row[0] for row in rows]
        ticks = [row[1] for row in rows]
        tick_deltas = [b - a for a, b in zip(ticks, ticks[1:]) if b >= a]
        tick_buckets = defaultdict(int)
        for delta in tick_deltas:
            tick_buckets[delta if delta <= 4 else "5+"] += 1
        raw_swaps = defaultdict(int)
        effective_swaps = defaultdict(int)
        for _, _, _, raw, effective in rows:
            raw_swaps[raw] += 1
            effective_swaps[effective] += 1
        print(
            f"consumer={consumer} acquires={len(rows)} rawSwaps={dict(raw_swaps)} "
            f"effectiveSwaps={dict(effective_swaps)}"
        )
        print("  host cadence:", summarize_deltas(consecutive_deltas(host_times)))
        print(f"  compositor tick deltas: {dict(tick_buckets)}")

    print("\nA/B interpretation guide:")
    print("- ON + raw swap=3 + effective=2 but producer remains ~50ms => clamp does not create upstream frames; swap=3 is mainly a symptom")
    print("- ON + raw swap=3 + effective=2 and producer shifts into 33-50ms / 21-29fps => compositor release/acquire timing participates in a feedback ceiling")
    print("- any timing/render regression => reject the clamp as an optimization even if FPS rises")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
