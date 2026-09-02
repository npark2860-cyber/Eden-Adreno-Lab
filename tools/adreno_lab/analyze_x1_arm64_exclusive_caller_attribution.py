#!/usr/bin/env python3
# Analyze sampled higher-level callers of sdk InternalCriticalSection::Enter LDXR.

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import argparse
import re

MODULE_RE = re.compile(
    r"\[X1-WAKERH\] module=(?P<module>\S+) base=(?P<base>0x[0-9a-fA-F]+) "
    r"end=(?P<end>0x[0-9a-fA-F]+) size=(?P<size>0x[0-9a-fA-F]+)"
)
SUMMARY_RE = re.compile(
    r"\[X1-XEXCLCALL\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) producer=(?P<producer>\d+) "
    r"summary sampleRate=(?P<sample_rate>\d+) samples=(?P<samples>\d+) topSamples=(?P<top_samples>\d+) "
    r"coveragePermille=(?P<coverage>\d+) invalidStack=(?P<invalid>\d+) dropped=(?P<dropped>\d+) "
    r"occupied=(?P<occupied>\d+)"
)
RANK_RE = re.compile(
    r"\[X1-XEXCLCALL\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) producer=(?P<producer>\d+) "
    r"rank=(?P<rank>\d+) caller=(?P<caller>0x[0-9a-fA-F]+) samples=(?P<samples>\d+)"
)


@dataclass(frozen=True)
class ModuleRange:
    name: str
    base: int
    end: int


@dataclass(frozen=True)
class Summary:
    frame: int
    producer: int
    sample_rate: int
    samples: int
    top_samples: int
    coverage_permille: int
    invalid_stack: int
    dropped: int
    occupied: int


@dataclass(frozen=True)
class Rank:
    frame: int
    producer: int
    rank: int
    caller: int
    samples: int


def parse_frame_list(value: str) -> tuple[int, ...]:
    frames = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not frames:
        raise argparse.ArgumentTypeError("frame list must not be empty")
    return frames


def parse_log(path: Path) -> tuple[list[ModuleRange], list[Summary], list[Rank]]:
    modules: dict[str, ModuleRange] = {}
    summaries: list[Summary] = []
    ranks: list[Rank] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = MODULE_RE.search(line)
        if match:
            module = ModuleRange(
                match.group("module"), int(match.group("base"), 16), int(match.group("end"), 16)
            )
            modules[module.name] = module
            continue
        match = SUMMARY_RE.search(line)
        if match:
            summaries.append(
                Summary(
                    frame=int(match.group("frame")),
                    producer=int(match.group("producer")),
                    sample_rate=int(match.group("sample_rate")),
                    samples=int(match.group("samples")),
                    top_samples=int(match.group("top_samples")),
                    coverage_permille=int(match.group("coverage")),
                    invalid_stack=int(match.group("invalid")),
                    dropped=int(match.group("dropped")),
                    occupied=int(match.group("occupied")),
                )
            )
            continue
        match = RANK_RE.search(line)
        if match:
            ranks.append(
                Rank(
                    frame=int(match.group("frame")),
                    producer=int(match.group("producer")),
                    rank=int(match.group("rank")),
                    caller=int(match.group("caller"), 16),
                    samples=int(match.group("samples")),
                )
            )
    if not summaries:
        raise ValueError("no [X1-XEXCLCALL] summary records found")
    return sorted(modules.values(), key=lambda item: item.base), summaries, ranks


def normalize(address: int, modules: list[ModuleRange]) -> str:
    for module in modules:
        if module.base <= address < module.end:
            return f"{module.name}+0x{address - module.base:x}"
    return f"abs:0x{address:x}"


def aggregate(ranks: list[Rank], modules: list[ModuleRange], producer: int,
              frames: tuple[int, ...]) -> list[tuple[str, int]]:
    frame_set = set(frames)
    counts: dict[str, int] = defaultdict(int)
    for item in ranks:
        if item.producer == producer and item.frame in frame_set:
            counts[normalize(item.caller, modules)] += item.samples
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def ratio_text(slow: int, fast: int) -> str:
    if fast == 0:
        return "inf" if slow else "n/a"
    return f"{slow / fast:.3f}x"


def print_group(label: str, producer: int, frames: tuple[int, ...], summaries: list[Summary],
                ranks: list[Rank], modules: list[ModuleRange], top: int) -> dict[str, int]:
    frame_set = set(frames)
    selected = [item for item in summaries if item.producer == producer and item.frame in frame_set]
    if not selected:
        print(f"producer={producer} {label}: no selected windows")
        return {}
    total = sum(item.samples for item in selected)
    invalid = sum(item.invalid_stack for item in selected)
    dropped = sum(item.dropped for item in selected)
    top_samples = sum(item.top_samples for item in selected)
    coverage = 0.0 if total == 0 else top_samples * 100.0 / total
    print(
        f"producer={producer} {label} frames={','.join(str(frame) for frame in frames)} "
        f"samples={total} topCoverage={coverage:.2f}% invalidStack={invalid} dropped={dropped}"
    )
    rows = aggregate(ranks, modules, producer, frames)
    result: dict[str, int] = {}
    for index, (caller, samples) in enumerate(rows[:top]):
        result[caller] = samples
        share = 0.0 if total == 0 else samples * 100.0 / total
        print(f"  #{index + 1} {caller} samples={samples} share={share:.2f}%")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze sampled callers of sdk InternalCriticalSection::Enter"
    )
    parser.add_argument("log", type=Path)
    parser.add_argument("--fast", type=parse_frame_list, required=True,
                        help="comma-separated swap=2 report frames from this same run")
    parser.add_argument("--slow", type=parse_frame_list, required=True,
                        help="comma-separated swap=3 report frames from this same run")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    modules, summaries, ranks = parse_log(args.log)
    if modules:
        print("modules:")
        for module in modules:
            print(f"  {module.name}=0x{module.base:x}-0x{module.end:x}")

    producers = sorted({item.producer for item in summaries})
    for producer in producers:
        fast = print_group("fast", producer, args.fast, summaries, ranks, modules, args.top)
        slow = print_group("slow", producer, args.slow, summaries, ranks, modules, args.top)
        print(f"producer={producer} fast/slow caller comparison")
        callers = set(fast) | set(slow)
        rows = sorted(callers, key=lambda caller: max(fast.get(caller, 0), slow.get(caller, 0)),
                      reverse=True)
        for caller in rows[:args.top]:
            fast_count = fast.get(caller, 0)
            slow_count = slow.get(caller, 0)
            print(
                f"  {caller} samples {fast_count}->{slow_count} "
                f"ratio={ratio_text(slow_count, fast_count)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
