#!/usr/bin/env python3
'''Summarize [X1-UNIFORM-PAYLOAD] aggregate lines from an Eden runtime log.'''

from pathlib import Path
import re
import sys

PATTERN = re.compile(
    r"\[X1-UNIFORM-PAYLOAD\] frame=(\d+) frames=(\d+) samples=(\d+) "
    r"uniqueSamples=(\d+) repeatSamples=(\d+) sameFingerprint=(\d+) "
    r"changedFingerprint=(\d+) sameFrameSame=(\d+) sameFrameChanged=(\d+) "
    r"sampleOverflow=(\d+) sampleDenom=(\d+)"
)

FIELDS = (
    "samples",
    "uniqueSamples",
    "repeatSamples",
    "sameFingerprint",
    "changedFingerprint",
    "sameFrameSame",
    "sameFrameChanged",
    "sampleOverflow",
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_uniform_payload.py <eden-log>")

    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    rows = []
    for match in PATTERN.finditer(text):
        values = list(map(int, match.groups()))
        frame, frames = values[:2]
        metrics = dict(zip(FIELDS, values[2:10]))
        denom = values[10]
        rows.append((frame, frames, metrics, denom))

    if not rows:
        raise SystemExit("no [X1-UNIFORM-PAYLOAD] lines found")

    totals = {field: 0 for field in FIELDS}
    total_frames = 0
    for _, frames, metrics, _ in rows:
        total_frames += frames
        for field in FIELDS:
            totals[field] += metrics[field]

    repeats = totals["repeatSamples"]
    same = totals["sameFingerprint"]
    changed = totals["changedFingerprint"]
    print(f"reports={len(rows)} reportFramesSum={total_frames} sampleDenom={rows[-1][3]}")
    for field in FIELDS:
        print(f"{field}={totals[field]}")
    if repeats:
        print(f"sameFingerprint/repeatSamples={same / repeats:.6%}")
        print(f"changedFingerprint/repeatSamples={changed / repeats:.6%}")
    classified = same + changed
    if classified:
        print(f"classifiedRepeatSamples={classified}")
    if totals["samples"]:
        print(f"repeatSamples/samples={repeats / totals['samples']:.6%}")
        print(f"sampleOverflow/samples={totals['sampleOverflow'] / totals['samples']:.6%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
