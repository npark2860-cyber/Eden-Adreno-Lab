#!/usr/bin/env python3
"""Summarize [X1-ADDRARB] waits and [X1-ADDRSIG] exact-address wake ownership."""

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

SIG_HEAD = re.compile(
    r"\[X1-ADDRSIG\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) "
    r"addr=(?P<addr>0x[0-9a-fA-F]+) targetTid=(?P<target_tid>0x[0-9a-fA-F]+) "
    r"slots=(?P<slots>\d+) sigCalls=(?P<calls>\d+) waitBegin=(?P<wait_begin>\d+) "
    r"waitDone=(?P<wait_done>\d+) matched=(?P<matched>\d+) missing=(?P<missing>\d+) "
    r"noActive=(?P<no_active>\d+) overflow=(?P<overflow>\d+)"
)

SIG_TOP = re.compile(
    r"top(?P<rank>[0-3])=(?P<tid>0x[0-9a-fA-F]+)/(?P<type>[^/]+)/(?P<calls>\d+)x/"
    r"v(?P<value>-?\d+)/vvar(?P<vvar>\d+)/cnt(?P<count>-?\d+)/cvar(?P<cvar>\d+)/"
    r"during(?P<during>\d+)/w2s(?P<w2s_avg>[0-9.]+)avg/(?P<w2s_max>[0-9.]+)max/"
    r"match(?P<match>\d+)/s2e(?P<s2e_avg>[0-9.]+)avg/(?P<s2e_max>[0-9.]+)max"
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_address_arbiter_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    wait_rows = []
    signal_rows = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        head = HEAD.search(line)
        if head:
            tops = {int(m.group("rank")): m.groupdict() for m in TOP.finditer(line)}
            top0 = tops.get(0, {})
            wall = float(head.group("wall"))
            frames = int(head.group("frames"))
            total = float(head.group("total"))
            wait_rows.append(
                {
                    "frame": int(head.group("frame")),
                    "wall_per_frame": wall / frames if frames else 0.0,
                    "tid": head.group("tid"),
                    "slots": int(head.group("slots")),
                    "calls": int(head.group("calls")),
                    "done": int(head.group("done")),
                    "per_frame": total / frames if frames else 0.0,
                    "avg": float(head.group("avg")),
                    "overflow": int(head.group("overflow")),
                    "switch": int(head.group("switch")),
                    "addr": top0.get("addr", "0x0"),
                    "type": top0.get("type", "unknown"),
                    "top_calls": int(top0.get("calls", 0)),
                    "top_done": int(top0.get("done", 0)),
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

        sig = SIG_HEAD.search(line)
        if sig:
            tops = {int(m.group("rank")): m.groupdict() for m in SIG_TOP.finditer(line)}
            top0 = tops.get(0, {})
            signal_rows.append(
                {
                    "frame": int(sig.group("frame")),
                    "frames": int(sig.group("frames")),
                    "addr": sig.group("addr"),
                    "target_tid": sig.group("target_tid"),
                    "slots": int(sig.group("slots")),
                    "calls": int(sig.group("calls")),
                    "wait_begin": int(sig.group("wait_begin")),
                    "wait_done": int(sig.group("wait_done")),
                    "matched": int(sig.group("matched")),
                    "missing": int(sig.group("missing")),
                    "no_active": int(sig.group("no_active")),
                    "overflow": int(sig.group("overflow")),
                    "waker_tid": top0.get("tid", "0x0"),
                    "type": top0.get("type", "unknown"),
                    "top_calls": int(top0.get("calls", 0)),
                    "value": int(top0.get("value", 0)),
                    "value_var": int(top0.get("vvar", 0)),
                    "count": int(top0.get("count", 0)),
                    "count_var": int(top0.get("cvar", 0)),
                    "during": int(top0.get("during", 0)),
                    "w2s_avg": float(top0.get("w2s_avg", 0.0)),
                    "w2s_max": float(top0.get("w2s_max", 0.0)),
                    "match": int(top0.get("match", 0)),
                    "s2e_avg": float(top0.get("s2e_avg", 0.0)),
                    "s2e_max": float(top0.get("s2e_max", 0.0)),
                }
            )

    if not wait_rows and not signal_rows:
        raise SystemExit("no [X1-ADDRARB] or [X1-ADDRSIG] records found")

    if wait_rows:
        print("WAIT ATTRIBUTION")
        print(
            "frame wall/f tid slots calls done arb/f topAddr topType topCalls topDone "
            "topAvg topMax ok timeout other timeoutNs tvar inflight overflow switch"
        )
        for row in wait_rows:
            print(
                f"{row['frame']:5d} {row['wall_per_frame']:7.3f} {row['tid']:>5} "
                f"{row['slots']:5d} {row['calls']:5d} {row['done']:4d} {row['per_frame']:7.3f} "
                f"{row['addr']:>12} {row['type']:>7} {row['top_calls']:8d} {row['top_done']:7d} "
                f"{row['top_avg']:7.3f} {row['top_max']:7.3f} {row['ok']:3d} {row['timeouts']:7d} "
                f"{row['other']:5d} {row['timeout_ns']:9d} {row['timeout_var']:4d} "
                f"{row['inflight']:8d} {row['overflow']:8d} {row['switch']:6d}"
            )

    if signal_rows:
        if wait_rows:
            print()
        print("EXACT-ADDRESS SIGNAL OWNER")
        print(
            "frame addr target waker sigType sigCalls waitBegin waitDone matched missing noActive "
            "value vvar count cvar during w2sAvg w2sMax wakeMatch s2eAvg s2eMax slots overflow"
        )
        for row in signal_rows:
            print(
                f"{row['frame']:5d} {row['addr']:>12} {row['target_tid']:>6} {row['waker_tid']:>6} "
                f"{row['type']:>9} {row['calls']:8d} {row['wait_begin']:9d} {row['wait_done']:8d} "
                f"{row['matched']:7d} {row['missing']:7d} {row['no_active']:8d} "
                f"{row['value']:5d} {row['value_var']:4d} {row['count']:5d} {row['count_var']:4d} "
                f"{row['during']:6d} {row['w2s_avg']:7.3f} {row['w2s_max']:7.3f} "
                f"{row['match']:9d} {row['s2e_avg']:7.3f} {row['s2e_max']:7.3f} "
                f"{row['slots']:5d} {row['overflow']:8d}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
