#!/usr/bin/env python3
"""Summarize [X1-WAKERF] producer CPU/wait attribution."""

from pathlib import Path
import sys


def parse_value(value: str):
    if value.endswith("ms"):
        return float(value[:-2])
    if value.startswith("0x"):
        return int(value, 16)
    if value.endswith("x"):
        value = value[:-1]
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_line(line: str):
    marker = "[X1-WAKERF] "
    pos = line.find(marker)
    if pos < 0:
        return None
    row = {}
    for token in line[pos + len(marker):].split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key in ("next0", "next1") and "/" in value:
            tid, calls = value.split("/", 1)
            row[key + "Tid"] = int(tid, 16)
            row[key + "Calls"] = parse_value(calls)
        else:
            row[key] = parse_value(value)
    return row


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_waker_stage_f_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        row = parse_line(line)
        if row:
            rows.append(row)

    if not rows:
        raise SystemExit("no [X1-WAKERF] records found")

    print(
        "frame tracked next p tid signals intervals inter wait residual cpu runUnsched "
        "none sleep ipc sync cond arb susp malformed"
    )
    for row in rows:
        for prefix in ("p0", "p1"):
            malformed = (
                int(row.get(prefix + "malCpu", 0))
                + int(row.get(prefix + "malWait", 0))
                + int(row.get(prefix + "malInt", 0))
            )
            print(
                f"{int(row.get('frame', 0)):5d} "
                f"0x{int(row.get('trackedAddr', 0)):x} 0x{int(row.get('nextAddr', 0)):x} "
                f"{prefix[1]} 0x{int(row.get(prefix + 'Tid', 0)):x} "
                f"{int(row.get(prefix + 'signals', 0)):7d} {int(row.get(prefix + 'intervals', 0)):9d} "
                f"{float(row.get(prefix + 'interAvg', 0.0)):7.3f} "
                f"{float(row.get(prefix + 'waitAvg', 0.0)):7.3f} "
                f"{float(row.get(prefix + 'residualAvg', 0.0)):8.3f} "
                f"{float(row.get(prefix + 'cpuAvg', 0.0)):7.3f} "
                f"{float(row.get(prefix + 'runUnschedAvg', 0.0)):10.3f} "
                f"{float(row.get(prefix + 'none', 0.0)):7.1f} "
                f"{float(row.get(prefix + 'sleep', 0.0)):7.1f} "
                f"{float(row.get(prefix + 'ipc', 0.0)):7.1f} "
                f"{float(row.get(prefix + 'sync', 0.0)):7.1f} "
                f"{float(row.get(prefix + 'cond', 0.0)):7.1f} "
                f"{float(row.get(prefix + 'arb', 0.0)):7.1f} "
                f"{float(row.get(prefix + 'susp', 0.0)):7.1f} {malformed:9d}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
