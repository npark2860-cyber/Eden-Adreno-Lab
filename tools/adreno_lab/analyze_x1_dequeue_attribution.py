#!/usr/bin/env python3
'''Analyze X1 DequeueBuffer attribution records together with QueueBuffer cadence.'''

from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import statistics
from typing import Iterable


QUEUE_RE = re.compile(
    r"\[X1-CADENCE\]\[QUEUE\].*?hostUs=(?P<host>\d+).*?core=0x(?P<core>[0-9a-fA-F]+)"
    r".*?frame=(?P<frame>\d+).*?slot=(?P<slot>-?\d+).*?swap=(?P<swap>-?\d+)"
)
BEGIN_RE = re.compile(
    r"\[X1-DEQUEUE\]\[BEGIN\].*?hostUs=(?P<host>\d+).*?callUs=(?P<call>\d+)"
    r".*?core=0x(?P<core>[0-9a-fA-F]+)"
)
SLOT_RE = re.compile(
    r"\[X1-DEQUEUE\]\[SLOT\].*?hostUs=(?P<host>\d+).*?callUs=(?P<call>\d+)"
    r".*?core=0x(?P<core>[0-9a-fA-F]+).*?slot=(?P<slot>-?\d+).*?"
    r"preSlotUs=(?P<pre>-?\d+).*?slotWaitUs=(?P<wait>-?\d+)"
)
END_RE = re.compile(
    r"\[X1-DEQUEUE\]\[END\].*?hostUs=(?P<host>\d+).*?callUs=(?P<call>\d+)"
    r".*?core=0x(?P<core>[0-9a-fA-F]+).*?slot=(?P<slot>-?\d+).*?"
    r"frame=(?P<frame>\d+).*?totalUs=(?P<total>-?\d+)"
)


@dataclass(frozen=True)
class QueueEvent:
    host_us: int
    core: str
    frame: int
    slot: int
    swap: int


@dataclass
class DequeueCall:
    call_us: int
    core: str
    begin_us: int
    slot_us: int | None = None
    slot: int | None = None
    pre_slot_us: int | None = None
    wait_us: int | None = None
    end_us: int | None = None
    total_us: int | None = None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def stats_ms(values_us: Iterable[int]) -> str:
    vals = [v / 1000.0 for v in values_us if v >= 0]
    if not vals:
        return "n=0"
    return (
        f"n={len(vals)} avg={statistics.fmean(vals):.3f}ms "
        f"median={statistics.median(vals):.3f}ms "
        f"p90={percentile(vals, 0.90):.3f}ms "
        f"p99={percentile(vals, 0.99):.3f}ms max={max(vals):.3f}ms"
    )


def parse(path: Path) -> tuple[list[QueueEvent], dict[tuple[str, int], DequeueCall]]:
    queues: list[QueueEvent] = []
    calls: dict[tuple[str, int], DequeueCall] = {}

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = QUEUE_RE.search(line)
        if m:
            queues.append(
                QueueEvent(
                    host_us=int(m["host"]),
                    core=m["core"].lower(),
                    frame=int(m["frame"]),
                    slot=int(m["slot"]),
                    swap=int(m["swap"]),
                )
            )
            continue

        m = BEGIN_RE.search(line)
        if m:
            key = (m["core"].lower(), int(m["call"]))
            calls[key] = DequeueCall(
                call_us=int(m["call"]),
                core=m["core"].lower(),
                begin_us=int(m["host"]),
            )
            continue

        m = SLOT_RE.search(line)
        if m:
            key = (m["core"].lower(), int(m["call"]))
            call = calls.get(key)
            if call:
                call.slot_us = int(m["host"])
                call.slot = int(m["slot"])
                call.pre_slot_us = int(m["pre"])
                call.wait_us = int(m["wait"])
            continue

        m = END_RE.search(line)
        if m:
            key = (m["core"].lower(), int(m["call"]))
            call = calls.get(key)
            if call:
                call.end_us = int(m["host"])
                call.slot = int(m["slot"])
                call.total_us = int(m["total"])

    queues.sort(key=lambda q: q.host_us)
    return queues, calls


def analyze(path: Path) -> None:
    queues, calls_by_key = parse(path)
    complete = [
        c
        for c in calls_by_key.values()
        if c.end_us is not None and c.slot is not None and c.total_us is not None
    ]
    if not queues:
        raise SystemExit("no [X1-CADENCE][QUEUE] records found")
    if not complete:
        raise SystemExit("no complete [X1-DEQUEUE] calls found")

    queue_counts = Counter(q.core for q in queues)
    call_counts = Counter(c.core for c in complete)
    common_cores = [core for core, _ in queue_counts.most_common() if call_counts[core] > 0]
    if not common_cores:
        raise SystemExit("no core contains both QueueBuffer and Dequeue records")
    core = common_cores[0]

    core_queues = [q for q in queues if q.core == core]
    core_calls = sorted((c for c in complete if c.core == core), key=lambda c: c.begin_us)
    queue_times = [q.host_us for q in core_queues]
    queues_by_slot: dict[int, list[QueueEvent]] = defaultdict(list)
    slot_times: dict[int, list[int]] = defaultdict(list)
    for q in core_queues:
        queues_by_slot[q.slot].append(q)
        slot_times[q.slot].append(q.host_us)

    cycles: list[dict[str, int]] = []
    for call in core_calls:
        prev_idx = bisect_left(queue_times, call.begin_us) - 1
        if prev_idx < 0:
            continue
        prev_q = core_queues[prev_idx]

        assert call.end_us is not None
        assert call.slot is not None
        times = slot_times.get(call.slot, [])
        events = queues_by_slot.get(call.slot, [])
        next_idx = bisect_left(times, call.end_us)
        if next_idx >= len(events):
            continue
        next_q = events[next_idx]

        if next_q.host_us - call.end_us > 500_000:
            continue

        cycles.append(
            {
                "swap": next_q.swap,
                "prev_queue_to_dequeue": call.begin_us - prev_q.host_us,
                "dequeue_total": int(call.total_us or 0),
                "pre_slot": int(call.pre_slot_us or 0),
                "slot_wait": int(call.wait_us or 0),
                "dequeue_to_next_queue": next_q.host_us - call.end_us,
                "queue_to_queue": next_q.host_us - prev_q.host_us,
            }
        )

    print(f"log: {path}")
    print(f"dominant core: 0x{core}")
    print(f"queue records: {len(core_queues)}")
    print(f"complete dequeue calls: {len(core_calls)}")
    print(f"paired producer cycles: {len(cycles)}")
    print()
    print("Dequeue service timing:")
    print(f"  total:     {stats_ms(c.total_us or 0 for c in core_calls)}")
    print(f"  pre-slot:  {stats_ms(c.pre_slot_us or 0 for c in core_calls)}")
    print(f"  slot wait: {stats_ms(c.wait_us or 0 for c in core_calls)}")

    if not cycles:
        return

    print()
    print("Producer-cycle split:")
    print("  previous Queue -> Dequeue BEGIN: " +
          stats_ms(c["prev_queue_to_dequeue"] for c in cycles))
    print("  Dequeue total:                 " +
          stats_ms(c["dequeue_total"] for c in cycles))
    print("  Dequeue END -> next Queue:     " +
          stats_ms(c["dequeue_to_next_queue"] for c in cycles))
    print("  Queue -> Queue total:          " +
          stats_ms(c["queue_to_queue"] for c in cycles))

    for swap in sorted({c["swap"] for c in cycles}):
        subset = [c for c in cycles if c["swap"] == swap]
        print()
        print(f"swap={swap} paired cycles: {len(subset)}")
        print("  Queue -> Dequeue: " +
              stats_ms(c["prev_queue_to_dequeue"] for c in subset))
        print("  Dequeue total:   " +
              stats_ms(c["dequeue_total"] for c in subset))
        print("  slot wait:       " +
              stats_ms(c["slot_wait"] for c in subset))
        print("  Dequeue -> Queue: " +
              stats_ms(c["dequeue_to_next_queue"] for c in subset))
        print("  Queue -> Queue:   " +
              stats_ms(c["queue_to_queue"] for c in subset))

    long_wait = sum(1 for c in cycles if c["slot_wait"] >= 5_000)
    long_guest = sum(1 for c in cycles if c["prev_queue_to_dequeue"] >= 20_000)
    long_render = sum(1 for c in cycles if c["dequeue_to_next_queue"] >= 20_000)
    print()
    print("Attribution counters:")
    print(f"  slotWait >=5ms:               {long_wait}/{len(cycles)}")
    print(f"  Queue->Dequeue >=20ms:        {long_guest}/{len(cycles)}")
    print(f"  Dequeue->next Queue >=20ms:   {long_render}/{len(cycles)}")
    print()
    print("Interpretation:")
    print("  - large Queue->Dequeue: guest/game pacing before requesting the next buffer")
    print("  - large slotWait/Dequeue total: BufferQueue free-slot backpressure")
    print("  - small Dequeue but large Dequeue->Queue: guest rendering/GPU production after dequeue")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    analyze(args.log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
