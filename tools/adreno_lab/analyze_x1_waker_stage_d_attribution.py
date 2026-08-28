#!/usr/bin/env python3
"""Summarize [X1-WAKERD] Stage D CPU/scheduler attribution."""

from pathlib import Path
import sys


def parse_value(value: str):
    if value.endswith("ms"):
        return float(value[:-2])
    if value.endswith("%"):
        return float(value[:-1])
    if value.startswith("0x"):
        return int(value, 16)
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_line(line: str):
    marker = "[X1-WAKERD] "
    pos = line.find(marker)
    if pos < 0:
        return None
    row = {}
    for token in line[pos + len(marker):].split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key.startswith("lr") and "/" in value:
            addr, count = value.split("/", 1)
            row[key + "Addr"] = int(addr, 16)
            row[key + "Count"] = int(count)
        else:
            row[key] = parse_value(value)
    return row


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_waker_stage_d_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        row = parse_line(line)
        if row:
            rows.append(row)

    if not rows:
        raise SystemExit("no [X1-WAKERD] records found")

    print(
        "frame waker interAvg waitAvg residualAvg cpuAvg runUnschedAvg "
        "none sleep ipc sync cond arb susp actNone coreNone userExc lr0 lr0N lr1 lr1N cpuOver malformed"
    )
    for row in rows:
        malformed = int(row.get("malformedCpu", 0)) + int(row.get("malformedWait", 0)) + int(
            row.get("malformedInterval", 0)
        )
        print(
            f"{int(row.get('frame', 0)):5d} 0x{int(row.get('wakerTid', 0)):x} "
            f"{float(row.get('interAvg', 0.0)):8.3f} {float(row.get('waitAvg', 0.0)):8.3f} "
            f"{float(row.get('residualAvg', 0.0)):11.3f} {float(row.get('cpuAvg', 0.0)):8.3f} "
            f"{float(row.get('runUnschedAvg', 0.0)):13.3f} {float(row.get('none', 0.0)):7.1f} "
            f"{float(row.get('sleep', 0.0)):7.1f} {float(row.get('ipc', 0.0)):7.1f} "
            f"{float(row.get('sync', 0.0)):7.1f} {float(row.get('cond', 0.0)):7.1f} "
            f"{float(row.get('arb', 0.0)):7.1f} {float(row.get('susp', 0.0)):7.1f} "
            f"{float(row.get('noneActivity', 0.0)):7.1f} {float(row.get('noneCoreMask', 0.0)):8.1f} "
            f"{float(row.get('noneUserExc', 0.0)):7.1f} "
            f"0x{int(row.get('lr0Addr', 0)):x} {int(row.get('lr0Count', 0)):4d} "
            f"0x{int(row.get('lr1Addr', 0)):x} {int(row.get('lr1Count', 0)):4d} "
            f"{int(row.get('cpuOverResidual', 0)):7d} {malformed:9d}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
