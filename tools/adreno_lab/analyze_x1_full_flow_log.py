#!/usr/bin/env python3
import argparse
from collections import defaultdict
from pathlib import Path
import re

SLOW = re.compile(
    r"\[X1-FLOW\]\[(?P<cat>[^\]]+)\].*?frame=(?P<frame>\d+)\s+thread=(?P<thread>\d+)\s+"
    r"reason=(?P<reason>\S+)\s+tick=(?P<tick>\d+)\s+aux=(?P<aux>\d+)\s+duration=(?P<ms>[0-9.]+)ms"
)
SUMMARY = re.compile(r"\[X1-FLOW\]\[(SCHED|PIPE|PRESENT|UPLOAD|QCOM)\]")
DBUF = re.compile(r"\[X1-DBUF\].*?frame=(?P<frame>\d+)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize Eden X1 full-flow profiler logs")
    ap.add_argument("log", type=Path)
    ap.add_argument("--top", type=int, default=20, help="slow events to print")
    args = ap.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    events = []
    by_cat = defaultdict(list)
    by_reason = defaultdict(list)
    last_summary = {}
    dbuf_lines = []

    for lineno, line in enumerate(lines, 1):
        m = SLOW.search(line)
        if m:
            row = {
                "line": lineno,
                "cat": m.group("cat"),
                "frame": int(m.group("frame")),
                "thread": int(m.group("thread")),
                "reason": m.group("reason"),
                "tick": int(m.group("tick")),
                "aux": int(m.group("aux")),
                "ms": float(m.group("ms")),
            }
            events.append(row)
            by_cat[row["cat"]].append(row["ms"])
            by_reason[(row["cat"], row["reason"])].append(row["ms"])

        s = SUMMARY.search(line)
        if s and "thread=" not in line:
            last_summary[s.group(1)] = (lineno, line.strip())

        if DBUF.search(line):
            dbuf_lines.append((lineno, line.strip()))

    print("X1 full-flow factual summary")
    print(f"log={args.log}")
    print(f"slow_events={len(events)}")

    if by_cat:
        print("\nSlow-event categories:")
        for cat in sorted(by_cat):
            vals = by_cat[cat]
            print(f"  {cat}: count={len(vals)} total={sum(vals):.3f}ms max={max(vals):.3f}ms")

    if by_reason:
        print("\nSlow-event reasons:")
        rows = sorted(by_reason.items(), key=lambda kv: sum(kv[1]), reverse=True)
        for (cat, reason), vals in rows:
            print(
                f"  {cat}/{reason}: count={len(vals)} total={sum(vals):.3f}ms "
                f"max={max(vals):.3f}ms"
            )

    if events:
        print(f"\nTop {min(args.top, len(events))} slow events:")
        for row in sorted(events, key=lambda r: r["ms"], reverse=True)[: args.top]:
            print(
                f"  {row['ms']:.3f}ms cat={row['cat']} reason={row['reason']} "
                f"frame={row['frame']} tick={row['tick']} thread={row['thread']} "
                f"aux={row['aux']} line={row['line']}"
            )

    if last_summary:
        print("\nLast aggregate line per category:")
        for cat in ("SCHED", "PIPE", "PRESENT", "UPLOAD", "QCOM"):
            if cat in last_summary:
                lineno, line = last_summary[cat]
                print(f"  line={lineno} {line}")

    if dbuf_lines:
        lineno, line = dbuf_lines[-1]
        print("\nLast descriptor-ring aggregate:")
        print(f"  line={lineno} {line}")

    if not events and not last_summary and not dbuf_lines:
        print(
            "\nNo [X1-FLOW] or [X1-DBUF] records found. Verify the desired GUI checkbox "
            "was enabled before launching the game."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
