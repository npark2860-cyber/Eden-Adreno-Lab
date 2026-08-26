#!/usr/bin/env python3
"""Summarize X1 Draw/Dispatch correlation logs.

Usage:
  python analyze_x1_draw_dispatch_log.py eden_log.txt
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import sys

SUMMARY_RE = re.compile(
    r"\[X1-FLOW\]\[ORIGIN\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) "
    r"draw=(?P<draw>\d+) upload=(?P<draw_upload>[0-9.]+)MiB "
    r"copy=(?P<draw_copy>\d+) (?P<draw_copy_mib>[0-9.]+)MiB "
    r"outside=(?P<draw_outside>\d+) barriers=(?P<draw_barriers>\d+) "
    r"wait=(?P<draw_wait>[0-9.]+)ms "
    r"dispatch=(?P<dispatch>\d+) upload=(?P<dispatch_upload>[0-9.]+)MiB "
    r"copy=(?P<dispatch_copy>\d+) (?P<dispatch_copy_mib>[0-9.]+)MiB "
    r"outside=(?P<dispatch_outside>\d+) barriers=(?P<dispatch_barriers>\d+) "
    r"wait=(?P<dispatch_wait>[0-9.]+)ms"
)

CALL_RE = re.compile(
    r"\[X1-FLOW\]\[ORIGIN-CALL\] frame=(?P<frame>\d+) thread=(?P<thread>\d+) "
    r"kind=(?P<kind>draw|dispatch) sig=0x(?P<sig>[0-9A-Fa-f]+) "
    r"upload=(?P<upload>[0-9.]+)MiB copy=(?P<copy>\d+) "
    r"(?P<copy_mib>[0-9.]+)MiB outside=(?P<outside>\d+) "
    r"barriers=(?P<barriers>\d+) wait=(?P<wait>[0-9.]+)ms"
)


@dataclass
class Totals:
    calls: int = 0
    upload_mib: float = 0.0
    copy_calls: int = 0
    copy_mib: float = 0.0
    outside: int = 0
    barriers: int = 0
    wait_ms: float = 0.0

    def add(self, calls: int, upload: float, copy_calls: int, copy_mib: float,
            outside: int, barriers: int, wait_ms: float) -> None:
        self.calls += calls
        self.upload_mib += upload
        self.copy_calls += copy_calls
        self.copy_mib += copy_mib
        self.outside += outside
        self.barriers += barriers
        self.wait_ms += wait_ms


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_draw_dispatch_log.py <eden_log.txt>")

    text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    totals = {"draw": Totals(), "dispatch": Totals()}
    heavy = []
    signature_counts = Counter()
    signature_cost = defaultdict(lambda: Totals())

    for line in text.splitlines():
        m = SUMMARY_RE.search(line)
        if m:
            totals["draw"].add(
                int(m["draw"]), float(m["draw_upload"]), int(m["draw_copy"]),
                float(m["draw_copy_mib"]), int(m["draw_outside"]),
                int(m["draw_barriers"]), float(m["draw_wait"]),
            )
            totals["dispatch"].add(
                int(m["dispatch"]), float(m["dispatch_upload"]), int(m["dispatch_copy"]),
                float(m["dispatch_copy_mib"]), int(m["dispatch_outside"]),
                int(m["dispatch_barriers"]), float(m["dispatch_wait"]),
            )
            continue

        m = CALL_RE.search(line)
        if m:
            row = {
                "frame": int(m["frame"]),
                "kind": m["kind"],
                "sig": m["sig"].upper().zfill(16),
                "upload": float(m["upload"]),
                "copy_calls": int(m["copy"]),
                "copy_mib": float(m["copy_mib"]),
                "outside": int(m["outside"]),
                "barriers": int(m["barriers"]),
                "wait": float(m["wait"]),
            }
            heavy.append(row)
            key = (row["kind"], row["sig"])
            signature_counts[key] += 1
            signature_cost[key].add(
                1, row["upload"], row["copy_calls"], row["copy_mib"],
                row["outside"], row["barriers"], row["wait"],
            )

    if not any(t.calls for t in totals.values()) and not heavy:
        print("No X1 Draw/Dispatch correlation records found.")
        return 2

    print("=== X1 Draw/Dispatch aggregate ===")
    for kind in ("draw", "dispatch"):
        t = totals[kind]
        per_call = lambda value: value / t.calls if t.calls else 0.0
        print(
            f"{kind:8s}: calls={t.calls:,} upload={t.upload_mib:.3f}MiB "
            f"copy={t.copy_calls:,}/{t.copy_mib:.3f}MiB outside={t.outside:,} "
            f"barriers={t.barriers:,} wait={t.wait_ms:.3f}ms | "
            f"per-call copy={per_call(t.copy_mib):.6f}MiB "
            f"outside={per_call(t.outside):.4f} barriers={per_call(t.barriers):.4f} "
            f"wait={per_call(t.wait_ms):.4f}ms"
        )

    if heavy:
        print("\n=== Top heavy individual calls ===")
        ranked = sorted(
            heavy,
            key=lambda r: (r["wait"], r["copy_mib"], r["outside"], r["barriers"]),
            reverse=True,
        )[:30]
        for row in ranked:
            print(
                f"frame={row['frame']:>6} {row['kind']:8s} sig=0x{row['sig']} "
                f"wait={row['wait']:8.3f}ms copy={row['copy_mib']:8.3f}MiB/{row['copy_calls']} "
                f"upload={row['upload']:8.3f}MiB outside={row['outside']:4d} "
                f"barriers={row['barriers']:4d}"
            )

        print("\n=== Repeating heavy signatures ===")
        for key, count in signature_counts.most_common(30):
            kind, sig = key
            t = signature_cost[key]
            print(
                f"{kind:8s} sig=0x{sig} hits={count:5d} "
                f"wait={t.wait_ms:9.3f}ms copy={t.copy_mib:9.3f}MiB "
                f"outside={t.outside:7d} barriers={t.barriers:7d}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
