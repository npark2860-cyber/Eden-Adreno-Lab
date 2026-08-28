#!/usr/bin/env python3
"""Summarize [X1-ADDRARB] 120-frame aggregates from an Eden runtime log."""

from pathlib import Path
import re
import sys


HEAD = re.compile(
    r"\[X1-ADDRARB\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) "
    r"wall=(?P<wall>[0-9.]+)ms tid=(?P<tid>0x[0-9a-fA-F]+) slots=(?P<slots>\d+) "
    r"calls=(?P<calls>\d+) done=(?P<done>\d+) total=(?P<total>[0-9.]+)ms "
    r"avg=(?P<avg>[0-9.]+)ms overflow=(?P<overflow>\d+) targetSwitch=(?P<switch>\d+)"
)

TOP = re.compile(
    r"top(?P<rank>[0-3])=(?P<addr>0x[0-9a-fA-F]+)/(?P<type>[^/]+)/"
    r"(?P<calls>\d+)x/(?P<done>\d+)done/(?P<total>[0-9.]+)ms/"
    r"(?P<avg>[0-9.]+)avg/(?P<max>[0-9.]+)max/ok(?P<ok>\d+)/to(?P<to>\d+)/"
    r"other(?P<other>\d+)/tns(?P<timeout>-?\d+)/tvar(?P<tvar>\d+)/in(?P<inflight>\d+)"
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_address_arbiter_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        head = HEAD.search(line)
        if not head:
            continue
        tops = {int(m.group("rank")): m.groupdict() for m in TOP.finditer(line)}
        top0 = tops.get(0, {})
        wall = float(head.group("wall"))
        frames = int(head.group("frames"))
        total = float(head.group("total"))
        rows.append(
            {
                "frame": int(head.group("frame")),
                "wall_per_frame": wall / frames if frames else 0.0,
                "tid": head.group("tid"),
                "slots": int(head.group("slots")),
                "calls": int(head.group("calls")),
                "done": int(head.group("done")),
                "total": total,
                "per_frame": total / frames if frames else 0.0,
                "avg": float(head.group("avg")),
                "overflow": int(head.group("overflow")),
                "switch": int(head.group("switch")),
                "addr": top0.get("addr", "0x0"),
                "type": top0.get("type", "unknown"),
                "top_calls": int(top0.get("calls", 0)),
                "top_done": int(top0.get("done", 0)),
                "top_total": float(top0.get("total", 0.0)),
                "top_avg": float(top0.get("avg", 0.0)),
                "top_max": float(top0.get("max", 0.0)),
                "ok": int(top0.get("ok", 0)),
                "timeouts": int(top0.get("to", 0)),
                "other": int(top0.get("other", 0)),
                "timeout_ns": int(top0.get("timeout", 0)),
                "timeout_var": int(top0.get("tvar", 0)),
                "inflight": int(top0.get("inflight", 0)),
            }
        )

    if not rows:
        raise SystemExit("no [X1-ADDRARB] records found")

    print(
        "frame wall/f tid slots calls done arb/f topAddr topType topCalls topDone "
        "topAvg topMax ok timeout other timeoutNs tvar inflight overflow switch"
    )
    for row in rows:
        print(
            f"{row['frame']:5d} {row['wall_per_frame']:7.3f} {row['tid']:>5} "
            f"{row['slots']:5d} {row['calls']:5d} {row['done']:4d} {row['per_frame']:7.3f} "
            f"{row['addr']:>12} {row['type']:>7} {row['top_calls']:8d} {row['top_done']:7d} "
            f"{row['top_avg']:7.3f} {row['top_max']:7.3f} {row['ok']:3d} {row['timeouts']:7d} "
            f"{row['other']:5d} {row['timeout_ns']:9d} {row['timeout_var']:4d} "
            f"{row['inflight']:8d} {row['overflow']:8d} {row['switch']:6d}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
