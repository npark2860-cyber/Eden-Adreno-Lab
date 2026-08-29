#!/usr/bin/env python3
"""Summarize [X1-WAKERG] focused producer CPU-slice PC/LR attribution."""

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


def parse_top(value: str):
    parts = value.split("/")
    if len(parts) != 6:
        raise ValueError(f"malformed top context: {value}")
    return {
        "pc": int(parts[0], 16),
        "lr": int(parts[1], 16),
        "ticks": int(parts[2]),
        "wall_ms": float(parts[3][:-2]) if parts[3].endswith("ms") else float(parts[3]),
        "slices": int(parts[4]),
        "share": float(parts[5][:-1]) if parts[5].endswith("%") else float(parts[5]),
    }


def parse_line(line: str):
    marker = "[X1-WAKERG] "
    pos = line.find(marker)
    if pos < 0:
        return None
    row = {}
    for token in line[pos + len(marker):].split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key.startswith("top"):
            row[key] = parse_top(value)
        else:
            row[key] = parse_value(value)
    return row


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_waker_stage_g_attribution.py <eden-log.txt>")

    path = Path(sys.argv[1])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        row = parse_line(line)
        if row:
            rows.append(row)

    if not rows:
        raise SystemExit("no [X1-WAKERG] records found")

    print(
        "frame producer tid slices cpuTicks cpuWall unknown overflow idSwitch missing malStart "
        "malTicks clockMismatch topPC topLR topTicks topShare"
    )
    for row in rows:
        top0 = row.get("top0", {"pc": 0, "lr": 0, "ticks": 0, "share": 0.0})
        print(
            f"{int(row.get('frame', 0)):5d} {int(row.get('producer', 0)):8d} "
            f"0x{int(row.get('tid', 0)):x} {int(row.get('slices', 0)):6d} "
            f"{int(row.get('cpuTicks', 0)):8d} {float(row.get('cpuWall', 0.0)):7.3f} "
            f"{int(row.get('unknownN', 0)):7d} {int(row.get('overflowN', 0)):8d} "
            f"{int(row.get('identitySwitch', 0)):8d} {int(row.get('missingStart', 0)):7d} "
            f"{int(row.get('malStart', 0)):8d} {int(row.get('malTicks', 0)):8d} "
            f"{int(row.get('clockMismatch', 0)):13d} 0x{int(top0['pc']):x} "
            f"0x{int(top0['lr']):x} {int(top0['ticks']):8d} {float(top0['share']):8.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
