#!/usr/bin/env python3
# Normalize Stage K caller contexts and map normalized work-target pairs to ModuleSystem components.

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import argparse
import re

MODULE_RE = re.compile(
    r"\[X1-WAKERH\] module=(?P<name>\S+) base=(?P<base>0x[0-9a-fA-F]+) "
    r"end=(?P<end>0x[0-9a-fA-F]+) size=(?P<size>0x[0-9a-fA-F]+)"
)
HEADER_RE = re.compile(r"\[X1-WAKERK\] frame=(?P<frame>\d+).*?producer=(?P<producer>\d+)")
TOP_RE = re.compile(
    r"top(?P<rank>[0-3])=(?P<pc>0x[0-9a-fA-F]+)/(?P<lr>0x[0-9a-fA-F]+)/"
    r"(?P<parent>0x[0-9a-fA-F]+)/(?P<grandparent>0x[0-9a-fA-F]+)/"
    r"(?P<ticks>\d+)/(?P<slices>\d+)/(?P<share>[0-9.]+)%"
)
WORK_SUMMARY_RE = re.compile(
    r"workResolvedN=(?P<resolved_n>\d+) workResolvedTicks=(?P<resolved_ticks>\d+) "
    r"workOtherResolvedTicks=(?P<other_ticks>\d+) "
    r"workOverflowN=(?P<overflow_n>\d+) workOverflowTicks=(?P<overflow_ticks>\d+)"
)
WORK_TOP_RE = re.compile(
    r"workTop(?P<rank>[0-3])=(?P<shim>0x[0-9a-fA-F]+)/(?P<work>0x[0-9a-fA-F]+)/"
    r"(?P<ticks>\d+)/(?P<slices>\d+)/(?P<share>[0-9.]+)%"
)

COMMON_MODULESYSTEM_SHIM = 0x2AF1230
STRICT_FAST_FRAMES = (960, 1080)
STRICT_SLOW_FRAMES = (1320, 1440, 1560, 1680)

# Static 41-slot table from DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md.
MODULESYSTEM_SLOTS = (
    (0, "System", 0x26A7FC0),
    (1, "DenguModule", 0x2AE7B14),
    (2, "Resource", 0x249D114),
    (3, "RSDB", 0x2AFAFB8),
    (4, "Graphics", 0xC9F1E4),
    (5, "Ltk", 0x2AF178C),
    (6, "Visualize", 0x2B01094),
    (7, "Controller", 0xD1D3F8),
    (8, "Rumble", 0xC0EAA4),
    (9, "Actor", 0xA85380),
    (10, "Transceiver", 0x12C1304),
    (11, "Banc", 0x2460BCC),
    (12, "Scene", 0x9370E8),
    (13, "AS", 0x2ADC5F4),
    (14, "AI", 0x2ADBB54),
    (15, "Physics", 0x2AF2BA0),
    (16, "ProgramHotReloadModule", 0x26A7FC0),
    (17, "unnamed#17", 0x26A7FC0),
    (18, "Event", 0x2488CF8),
    (19, "EventModuleWorker", 0x2488E04),
    (20, "EventModuleSubWorker", 0x2488FC0),
    (21, "EventModuleSubWorker", 0x2488FC0),
    (22, "UI", 0x869624),
    (23, "Effect", 0xC1C28C),
    (24, "Sound", 0x9BC044),
    (25, "XLink", 0xD51F6C),
    (26, "Reaction", 0xBD1B68),
    (27, "Terrain", 0x12B6D4C),
    (28, "ECppModule", 0x2AF1554),
    (29, "SpyLog", 0x2AFC46C),
    (30, "GameData", 0xEE96CC),
    (31, "Blackboard", 0x9143F4),
    (32, "LuaModule", 0x26A7FC0),
    (33, "Tool", 0x1219F54),
    (34, "Camera", 0x1015FFC),
    (35, "REC", 0x2AF1648),
    (36, "LOD", 0x77FA74),
    (37, "unnamed#37", 0x26A7FC0),
    (38, "Bake", 0xF6A020),
    (39, "Rail", 0x2AF3CBC),
    (40, "PlayReport", 0xAD231C),
)

TARGET_TO_COMPONENTS: dict[int, tuple[str, ...]] = {}
_target_names: dict[int, list[str]] = defaultdict(list)
for _slot, _name, _target in MODULESYSTEM_SLOTS:
    if _name not in _target_names[_target]:
        _target_names[_target].append(_name)
TARGET_TO_COMPONENTS = {target: tuple(names) for target, names in _target_names.items()}


@dataclass(frozen=True)
class ModuleRange:
    name: str
    base: int
    end: int

    def resolve(self, address: int) -> str | None:
        if self.base <= address < self.end:
            return f"{self.name}+0x{address - self.base:x}"
        return None


@dataclass(frozen=True)
class WorkPair:
    rank: int
    shim_offset: int
    work_offset: int
    ticks: int
    slices: int
    share: float


@dataclass
class WorkWindow:
    frame: int
    producer: int
    resolved_n: int
    resolved_ticks: int
    other_ticks: int
    overflow_n: int
    overflow_ticks: int
    pairs: list[WorkPair]


def parse_modules(lines: list[str]) -> list[ModuleRange]:
    modules: list[ModuleRange] = []
    for line in lines:
        match = MODULE_RE.search(line)
        if not match:
            continue
        base = int(match.group("base"), 16)
        end = int(match.group("end"), 16)
        size = int(match.group("size"), 16)
        if end <= base or end - base != size:
            raise ValueError(f"invalid module range: {line.strip()}")
        modules.append(ModuleRange(match.group("name"), base, end))
    if not modules:
        raise ValueError("no [X1-WAKERH] module ranges found")
    modules.sort(key=lambda item: item.base)
    for previous, current in zip(modules, modules[1:]):
        if previous.end > current.base:
            raise ValueError(f"overlapping module ranges: {previous.name} and {current.name}")
    return modules


def resolve(modules: list[ModuleRange], address: int) -> str:
    if address == 0:
        return "zero"
    for module in modules:
        identity = module.resolve(address)
        if identity is not None:
            return identity
    return f"unmapped@0x{address:x}"


def component_identity(shim_offset: int, work_offset: int) -> str:
    if shim_offset != COMMON_MODULESYSTEM_SHIM:
        return f"nonModuleSystemShim(main+0x{shim_offset:x})"
    names = TARGET_TO_COMPONENTS.get(work_offset)
    if names is None:
        return f"unmappedModuleSystemTarget(main+0x{work_offset:x})"
    return "|".join(names)


def print_strict_summary(windows: list[WorkWindow]) -> None:
    if not windows:
        return
    by_producer: dict[int, dict[int, WorkWindow]] = defaultdict(dict)
    for window in windows:
        by_producer[window.producer][window.frame] = window

    cadence_defs = (("fast/swap2", STRICT_FAST_FRAMES), ("slow/swap3", STRICT_SLOW_FRAMES))
    cadence_component_avg: dict[tuple[int, str], dict[int, float]] = {}

    for producer in sorted(by_producer):
        for cadence, expected_frames in cadence_defs:
            selected = [by_producer[producer][frame] for frame in expected_frames
                        if frame in by_producer[producer]]
            if not selected:
                continue
            count = len(selected)
            resolved_avg = sum(item.resolved_ticks for item in selected) / count
            other_avg = sum(item.other_ticks for item in selected) / count
            overflow_avg = sum(item.overflow_ticks for item in selected) / count
            common_ticks: dict[int, int] = defaultdict(int)
            reported_common_total = 0
            for item in selected:
                for pair in item.pairs:
                    if pair.shim_offset != COMMON_MODULESYSTEM_SHIM:
                        continue
                    common_ticks[pair.work_offset] += pair.ticks
                    reported_common_total += pair.ticks
            reported_common_avg = reported_common_total / count
            coverage_lower = 0.0 if resolved_avg == 0 else reported_common_avg * 100.0 / resolved_avg
            found_frames = ",".join(str(item.frame) for item in selected)
            print(
                f"strict producer={producer} cadence={cadence} windows={count}/{len(expected_frames)} "
                f"frames={found_frames} resolvedAvgTicks={resolved_avg:.1f} "
                f"otherResolvedAvgTicks={other_avg:.1f} overflowAvgTicks={overflow_avg:.1f} "
                f"reportedCommonShimAvgTicks={reported_common_avg:.1f} "
                f"reportedCommonCoverageLower={coverage_lower:.2f}%"
            )
            avg_by_target = {target: ticks / count for target, ticks in common_ticks.items()}
            cadence_component_avg[(producer, cadence)] = avg_by_target
            for target, avg_ticks in sorted(avg_by_target.items(), key=lambda item: item[1], reverse=True):
                print(
                    f"strictTarget producer={producer} cadence={cadence} "
                    f"work=main+0x{target:x} component={component_identity(COMMON_MODULESYSTEM_SHIM, target)} "
                    f"visibleTop4AvgTicksLower={avg_ticks:.1f}"
                )

        fast_key = (producer, "fast/swap2")
        slow_key = (producer, "slow/swap3")
        if fast_key not in cadence_component_avg or slow_key not in cadence_component_avg:
            continue
        fast = cadence_component_avg[fast_key]
        slow = cadence_component_avg[slow_key]
        for target in sorted(set(fast) | set(slow)):
            fast_ticks = fast.get(target, 0.0)
            slow_ticks = slow.get(target, 0.0)
            if fast_ticks == 0.0:
                ratio = "inf" if slow_ticks > 0.0 else "n/a"
            else:
                ratio = f"{slow_ticks / fast_ticks:.3f}x"
            print(
                f"strictRatio producer={producer} work=main+0x{target:x} "
                f"component={component_identity(COMMON_MODULESYSTEM_SHIM, target)} "
                f"fastVisibleAvgLower={fast_ticks:.1f} slowVisibleAvgLower={slow_ticks:.1f} "
                f"slowFastVisibleLowerRatio={ratio}"
            )


def analyze(path: Path) -> int:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    modules = parse_modules(lines)
    context_count = 0
    work_windows: list[WorkWindow] = []

    for line in lines:
        header = HEADER_RE.search(line)
        if not header:
            continue
        frame = int(header.group("frame"))
        producer = int(header.group("producer"))
        for top in TOP_RE.finditer(line):
            rank = int(top.group("rank"))
            pc = int(top.group("pc"), 16)
            lr = int(top.group("lr"), 16)
            parent = int(top.group("parent"), 16)
            grandparent = int(top.group("grandparent"), 16)
            ticks = int(top.group("ticks"))
            slices = int(top.group("slices"))
            share = float(top.group("share"))
            print(
                f"frame={frame} producer={producer} rank={rank} "
                f"pc={resolve(modules, pc)} rawPc=0x{pc:x} "
                f"lr={resolve(modules, lr)} rawLr=0x{lr:x} "
                f"parent={resolve(modules, parent)} rawParent=0x{parent:x} "
                f"grandparent={resolve(modules, grandparent)} rawGrandparent=0x{grandparent:x} "
                f"ticks={ticks} slices={slices} share={share:.2f}%"
            )
            context_count += 1

        summary = WORK_SUMMARY_RE.search(line)
        if not summary:
            continue
        pairs: list[WorkPair] = []
        for top in WORK_TOP_RE.finditer(line):
            pair = WorkPair(
                rank=int(top.group("rank")),
                shim_offset=int(top.group("shim"), 16),
                work_offset=int(top.group("work"), 16),
                ticks=int(top.group("ticks")),
                slices=int(top.group("slices")),
                share=float(top.group("share")),
            )
            if pair.ticks == 0:
                continue
            pairs.append(pair)
            print(
                f"work frame={frame} producer={producer} rank={pair.rank} "
                f"shim=main+0x{pair.shim_offset:x} work=main+0x{pair.work_offset:x} "
                f"component={component_identity(pair.shim_offset, pair.work_offset)} "
                f"ticks={pair.ticks} slices={pair.slices} share={pair.share:.2f}%"
            )
        work_windows.append(
            WorkWindow(
                frame=frame,
                producer=producer,
                resolved_n=int(summary.group("resolved_n")),
                resolved_ticks=int(summary.group("resolved_ticks")),
                other_ticks=int(summary.group("other_ticks")),
                overflow_n=int(summary.group("overflow_n")),
                overflow_ticks=int(summary.group("overflow_ticks")),
                pairs=pairs,
            )
        )

    if context_count == 0:
        raise ValueError("no [X1-WAKERK] top contexts found")
    if work_windows:
        print_strict_summary(work_windows)
    else:
        print("work-target identity fields not present in this Stage K log")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Stage K grandparent contexts and ModuleSystem work targets"
    )
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    return analyze(args.log)


if __name__ == "__main__":
    raise SystemExit(main())
