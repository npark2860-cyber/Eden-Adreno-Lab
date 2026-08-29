#!/usr/bin/env python3
# Normalize Stage J selected-producer PC/LR/parent-LR contexts with Stage H module ranges.

from dataclasses import dataclass
from pathlib import Path
import argparse
import re

MODULE_RE = re.compile(
    r"\[X1-WAKERH\] module=(?P<name>\S+) base=(?P<base>0x[0-9a-fA-F]+) "
    r"end=(?P<end>0x[0-9a-fA-F]+) size=(?P<size>0x[0-9a-fA-F]+)"
)
HEADER_RE = re.compile(r"\[X1-WAKERJ\] frame=(?P<frame>\d+).*?producer=(?P<producer>\d+)")
TOP_RE = re.compile(
    r"top(?P<rank>[0-3])=(?P<pc>0x[0-9a-fA-F]+)/(?P<lr>0x[0-9a-fA-F]+)/"
    r"(?P<parent>0x[0-9a-fA-F]+)/(?P<ticks>\d+)/(?P<slices>\d+)/(?P<share>[0-9.]+)%"
)


@dataclass(frozen=True)
class ModuleRange:
    name: str
    base: int
    end: int

    def resolve(self, address: int) -> str | None:
        if self.base <= address < self.end:
            return f"{self.name}+0x{address - self.base:x}"
        return None


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


def analyze(path: Path) -> int:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    modules = parse_modules(lines)
    count = 0
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
            ticks = int(top.group("ticks"))
            slices = int(top.group("slices"))
            share = float(top.group("share"))
            print(
                f"frame={frame} producer={producer} rank={rank} "
                f"pc={resolve(modules, pc)} rawPc=0x{pc:x} "
                f"lr={resolve(modules, lr)} rawLr=0x{lr:x} "
                f"parent={resolve(modules, parent)} rawParent=0x{parent:x} "
                f"ticks={ticks} slices={slices} share={share:.2f}%"
            )
            count += 1
    if count == 0:
        raise ValueError("no [X1-WAKERJ] top contexts found")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Stage J parent caller contexts")
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    return analyze(args.log)


if __name__ == "__main__":
    raise SystemExit(main())
