#!/usr/bin/env python3
"""Summarize [X1-WAKERE] recursive waker AddressArbiter attribution."""

from pathlib import Path
import re
import sys


TOP_RE = re.compile(
    r"(?P<addr>0x[0-9a-fA-F]+)/t(?P<type>\d+)/(?P<calls>\d+)x/(?P<done>\d+)done/"
    r"(?P<total>[0-9.]+)ms/(?P<avg>[0-9.]+)avg/(?P<max>[0-9.]+)max/"
    r"v(?P<value>-?\d+)/tns(?P<timeout>-?\d+)/vvar(?P<vvar>\d+)/tvar(?P<tvar>\d+)/"
    r"ok(?P<ok>\d+)/to(?P<to>\d+)/other(?P<other>\d+)"
)

SIG_RE = re.compile(
    r"(?P<tid>0x[0-9a-fA-F]+)/t(?P<type>\d+)/(?P<calls>\d+)x/during(?P<during>\d+)/"
    r"w2s(?P<w2s>[0-9.]+)avg/(?P<w2smax>[0-9.]+)max/"
    r"s2e(?P<s2e>[0-9.]+)avg/(?P<s2emax>[0-9.]+)max/"
    r"v(?P<value>-?\d+)/cnt(?P<count>-?\d+)/vvar(?P<vvar>\d+)/cvar(?P<cvar>\d+)"
)


def token_value(text: str, key: str, default: str = "0") -> str:
    match = re.search(rf"(?:^|\s){re.escape(key)}=([^\s]+)", text)
    return match.group(1) if match else default


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_waker_stage_e_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = "[X1-WAKERE] "
        pos = line.find(marker)
        if pos < 0:
            continue
        body = line[pos + len(marker):]
        top0_raw = token_value(body, "top0", "")
        sig0_raw = token_value(body, "sig0", "")
        top0 = TOP_RE.fullmatch(top0_raw)
        sig0 = SIG_RE.fullmatch(sig0_raw)
        rows.append(
            {
                "frame": int(token_value(body, "frame")),
                "waker": int(token_value(body, "wakerTid"), 16),
                "wait_ms": float(token_value(body, "wait", "0ms")[:-2]),
                "promoted": int(token_value(body, "promoted"), 16),
                "next": int(token_value(body, "nextPromoted"), 16),
                "switch": int(token_value(body, "promotedSwitch")),
                "top0": top0.groupdict() if top0 else None,
                "sig0": sig0.groupdict() if sig0 else None,
                "sig_calls": int(token_value(body, "sigCalls")),
                "no_active": int(token_value(body, "noActive")),
                "wait_done": int(token_value(body, "promotedWaitDone")),
                "no_signal": int(token_value(body, "noSignalReturn")),
                "wait_overflow": int(token_value(body, "waitOverflow")),
                "signal_overflow": int(token_value(body, "signalOverflow")),
                "nested": int(token_value(body, "nestedWait")),
                "malformed": int(token_value(body, "malformedWait")),
            }
        )

    if not rows:
        raise SystemExit("no [X1-WAKERE] records found")

    print(
        "frame waker promoted next topAddr type calls done totalMs avgMs maxMs value timeout "
        "sigTid sigType sigCalls during w2sAvg s2eAvg noActive noSignal ovf"
    )
    for row in rows:
        top = row["top0"] or {}
        sig = row["sig0"] or {}
        overflow = row["wait_overflow"] + row["signal_overflow"] + row["nested"] + row["malformed"]
        print(
            f"{row['frame']:5d} 0x{row['waker']:x} 0x{row['promoted']:x} 0x{row['next']:x} "
            f"{top.get('addr', '0x0'):>12} {int(top.get('type', 0)):4d} "
            f"{int(top.get('calls', 0)):5d} {int(top.get('done', 0)):5d} "
            f"{float(top.get('total', 0.0)):8.3f} {float(top.get('avg', 0.0)):7.3f} "
            f"{float(top.get('max', 0.0)):7.3f} {int(top.get('value', 0)):6d} "
            f"{int(top.get('timeout', 0)):8d} {sig.get('tid', '0x0'):>8} "
            f"{int(sig.get('type', 0)):7d} {row['sig_calls']:8d} {int(sig.get('during', 0)):6d} "
            f"{float(sig.get('w2s', 0.0)):7.3f} {float(sig.get('s2e', 0.0)):7.3f} "
            f"{row['no_active']:8d} {row['no_signal']:8d} {overflow:3d}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
