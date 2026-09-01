#!/usr/bin/env python3
# Analyze sampled 32-bit LDXR guest-PC attribution for the two Stage F producers.

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
    r"\[X1-XEXCLPC\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) producer=(?P<producer>\d+) "
    r"summary sampleRate=(?P<sample_rate>\d+) samples=(?P<samples>\d+) sampleNs=(?P<sample_ns>\d+) "
    r"topSamples=(?P<top_samples>\d+) topNs=(?P<top_ns>\d+) "
    r"coveragePermille=(?P<coverage>\d+) dropped=(?P<dropped>\d+) occupied=(?P<occupied>\d+)"
)
RANK_RE = re.compile(
    r"\[X1-XEXCLPC\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) producer=(?P<producer>\d+) "
    r"rank=(?P<rank>\d+) pc=(?P<pc>0x[0-9a-fA-F]+) samples=(?P<samples>\d+) "
    r"sampleNs=(?P<sample_ns>\d+) sampleAvgNs=(?P<sample_avg_ns>\d+)"
)

DEFAULT_FAST = (960, 1080)
DEFAULT_SLOW = (1320, 1440, 1560)


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
    sample_ns: int
    top_samples: int
    top_ns: int
    coverage_permille: int
    dropped: int
    occupied: int


@dataclass(frozen=True)
class Rank:
    frame: int
    producer: int
    rank: int
    pc: int
    samples: int
    sample_ns: int
    sample_avg_ns: int


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
                name=match.group("module"),
                base=int(match.group("base"), 16),
                end=int(match.group("end"), 16),
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
                    sample_ns=int(match.group("sample_ns")),
                    top_samples=int(match.group("top_samples")),
                    top_ns=int(match.group("top_ns")),
                    coverage_permille=int(match.group("coverage")),
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
                    pc=int(match.group("pc"), 16),
                    samples=int(match.group("samples")),
                    sample_ns=int(match.group("sample_ns")),
                    sample_avg_ns=int(match.group("sample_avg_ns")),
                )
            )
    if not summaries or not ranks:
        raise ValueError("no [X1-XEXCLPC] summary/rank records found")
    return sorted(modules.values(), key=lambda item: item.base), summaries, ranks


def normalize_pc(pc: int, modules: list[ModuleRange]) -> str:
    for module in modules:
        if module.base <= pc < module.end:
            return f"{module.name}+0x{pc - module.base:x}"
    return f"abs:0x{pc:x}"


def selected_frames(values: tuple[int, ...], present: set[int]) -> tuple[int, ...]:
    return tuple(frame for frame in values if frame in present)


def aggregate_sites(
    ranks: list[Rank], modules: list[ModuleRange], producer: int, frames: tuple[int, ...]
) -> list[tuple[str, int, int]]:
    by_site: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    frame_set = set(frames)
    for item in ranks:
        if item.producer != producer or item.frame not in frame_set:
            continue
        site = normalize_pc(item.pc, modules)
        by_site[site][0] += item.samples
        by_site[site][1] += item.sample_ns
    return sorted(
        ((site, values[0], values[1]) for site, values in by_site.items()),
        key=lambda item: (item[2], item[1]),
        reverse=True,
    )


def ratio_text(slow: float, fast: float) -> str:
    if fast == 0:
        return "inf" if slow > 0 else "n/a"
    return f"{slow / fast:.3f}x"


def print_group(
    label: str,
    producer: int,
    frames: tuple[int, ...],
    summaries: list[Summary],
    ranks: list[Rank],
    modules: list[ModuleRange],
    top: int,
) -> dict[str, tuple[int, int]]:
    frame_set = set(frames)
    selected_summary = [
        item for item in summaries if item.producer == producer and item.frame in frame_set
    ]
    if not selected_summary:
        print(f"producer={producer} {label}: no selected windows")
        return {}
    total_samples = sum(item.samples for item in selected_summary)
    total_ns = sum(item.sample_ns for item in selected_summary)
    top_ns = sum(item.top_ns for item in selected_summary)
    dropped = sum(item.dropped for item in selected_summary)
    coverage = 0.0 if total_ns == 0 else top_ns * 100.0 / total_ns
    print(
        f"producer={producer} {label} frames={','.join(str(frame) for frame in frames)} "
        f"sampled={total_samples} sampleNs={total_ns} topCoverage={coverage:.2f}% dropped={dropped}"
    )
    sites = aggregate_sites(ranks, modules, producer, frames)
    result: dict[str, tuple[int, int]] = {}
    for rank_index, (site, samples, sample_ns) in enumerate(sites[:top]):
        result[site] = (samples, sample_ns)
        avg_ns = 0.0 if samples == 0 else sample_ns / samples
        share = 0.0 if total_ns == 0 else sample_ns * 100.0 / total_ns
        print(
            f"  #{rank_index + 1} {site} samples={samples} sampleNs={sample_ns} "
            f"avgNs={avg_ns:.1f} share={share:.2f}%"
        )
    return result


def print_fast_slow_compare(
    producer: int,
    fast_sites: dict[str, tuple[int, int]],
    slow_sites: dict[str, tuple[int, int]],
    top: int,
) -> None:
    sites = set(fast_sites) | set(slow_sites)
    rows = []
    for site in sites:
        fast_samples, fast_ns = fast_sites.get(site, (0, 0))
        slow_samples, slow_ns = slow_sites.get(site, (0, 0))
        rows.append((site, fast_samples, fast_ns, slow_samples, slow_ns))
    rows.sort(key=lambda row: max(row[2], row[4]), reverse=True)
    print(f"producer={producer} fast/slow site comparison")
    for site, fast_samples, fast_ns, slow_samples, slow_ns in rows[:top]:
        print(
            f"  {site} samples {fast_samples}->{slow_samples} ratio={ratio_text(slow_samples, fast_samples)} "
            f"sampleNs {fast_ns}->{slow_ns} ratio={ratio_text(slow_ns, fast_ns)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze sampled 32-bit LDXR guest-PC attribution for X1 producers"
    )
    parser.add_argument("log", type=Path)
    parser.add_argument("--fast", type=parse_frame_list, default=DEFAULT_FAST)
    parser.add_argument("--slow", type=parse_frame_list, default=DEFAULT_SLOW)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    modules, summaries, ranks = parse_log(args.log)
    if modules:
        print("modules:")
        for module in modules:
            print(f"  {module.name}=0x{module.base:x}-0x{module.end:x}")

    present_by_producer: dict[int, set[int]] = defaultdict(set)
    for item in summaries:
        present_by_producer[item.producer].add(item.frame)

    for producer in sorted(present_by_producer):
        fast_frames = selected_frames(args.fast, present_by_producer[producer])
        slow_frames = selected_frames(args.slow, present_by_producer[producer])
        fast_sites = print_group(
            "fast", producer, fast_frames, summaries, ranks, modules, args.top
        )
        slow_sites = print_group(
            "slow", producer, slow_frames, summaries, ranks, modules, args.top
        )
        print_fast_slow_compare(producer, fast_sites, slow_sites, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
