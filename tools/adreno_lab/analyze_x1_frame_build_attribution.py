#!/usr/bin/env python3
'''Analyze [X1-FRAMEBUILD] aggregate timing records.

Usage:
  python analyze_x1_frame_build_attribution.py eden_log.txt

Each record already represents a 120-render-frame window. The analyzer converts aggregate
milliseconds to milliseconds per frame and ranks the measured top-level contributors and
GraphicsPipeline::Configure sub-stages.
'''

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import statistics
import sys


LINE_RE = re.compile(r"\[X1-FRAMEBUILD\]\s+(?P<body>.*)$")
TOKEN_RE = re.compile(r"([A-Za-z][A-Za-z0-9]*)=([^\s]+)")


@dataclass
class Record:
    frame: int
    frames: int
    values: dict[str, float]


def parse_number(raw: str) -> float:
    raw = raw.removesuffix("ms")
    return float(raw)


def parse(path: Path) -> list[Record]:
    records: list[Record] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_RE.search(line)
        if not match:
            continue
        tokens = dict(TOKEN_RE.findall(match.group("body")))
        if "frame" not in tokens or "frames" not in tokens:
            continue
        frame = int(tokens.pop("frame"))
        frames = int(tokens.pop("frames"))
        values: dict[str, float] = {}
        for key, value in tokens.items():
            try:
                values[key] = parse_number(value)
            except ValueError:
                pass
        records.append(Record(frame=frame, frames=frames, values=values))
    return records


def per_frame(record: Record, key: str) -> float:
    if record.frames <= 0:
        return 0.0
    return record.values.get(key, 0.0) / record.frames


def median_pf(records: list[Record], key: str) -> float:
    vals = [per_frame(r, key) for r in records]
    return statistics.median(vals) if vals else 0.0


def print_record(record: Record) -> None:
    top_keys = [
        "draw",
        "dispatch",
        "drawTexture",
        "clear",
        "flushCmd",
        "tick",
    ]
    cfg_keys = [
        "syncDesc",
        "stageScan",
        "fillViews",
        "bindViews",
        "buffers",
        "descPrep",
        "cfgDraw",
    ]
    draw_keys = ["flush", "mem", "preCfg", "cfg", "post"]

    print(f"frame={record.frame} window={record.frames}")
    print("  top-level ms/frame:")
    for key in sorted(top_keys, key=lambda k: per_frame(record, k), reverse=True):
        print(f"    {key:12s} {per_frame(record, key):9.3f}")

    print("  PrepareDraw split ms/frame:")
    for key in sorted(draw_keys, key=lambda k: per_frame(record, k), reverse=True):
        print(f"    {key:12s} {per_frame(record, key):9.3f}")

    print("  Graphics Configure split ms/frame:")
    for key in sorted(cfg_keys, key=lambda k: per_frame(record, k), reverse=True):
        print(f"    {key:12s} {per_frame(record, key):9.3f}")

    draw_calls = record.values.get("drawCalls", 0.0)
    gfx_calls = record.values.get("gfxCfgCalls", 0.0)
    dispatch_calls = record.values.get("dispatchCalls", 0.0)
    print(
        f"  calls/frame: draw={draw_calls / record.frames:.2f} "
        f"gfxCfg={gfx_calls / record.frames:.2f} "
        f"dispatch={dispatch_calls / record.frames:.2f}"
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_x1_frame_build_attribution.py <eden-log>")

    path = Path(sys.argv[1])
    records = parse(path)
    if not records:
        raise SystemExit("no [X1-FRAMEBUILD] records found")

    print(f"records={len(records)} frames={records[0].frame}..{records[-1].frame}")
    print()
    for record in records:
        print_record(record)
        print()

    print("median across report windows (ms/frame):")
    summary_keys = [
        "draw",
        "dispatch",
        "drawTexture",
        "clear",
        "flushCmd",
        "tick",
        "flush",
        "mem",
        "preCfg",
        "cfg",
        "post",
        "syncDesc",
        "stageScan",
        "fillViews",
        "bindViews",
        "buffers",
        "descPrep",
        "cfgDraw",
    ]
    ranked = sorted(summary_keys, key=lambda k: median_pf(records, k), reverse=True)
    for key in ranked:
        print(f"  {key:12s} {median_pf(records, key):9.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
