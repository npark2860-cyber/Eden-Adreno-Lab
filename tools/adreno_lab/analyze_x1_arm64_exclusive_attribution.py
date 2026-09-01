#!/usr/bin/env python3
# Analyze selected-producer ARM64 exclusive read/write attribution windows.

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import argparse
import re

LINE_RE = re.compile(
    r"\[X1-XEXCL\] frame=(?P<frame>\d+) frames=(?P<frames>\d+) producer=(?P<producer>\d+) "
    r"attempts=(?P<attempts>\d+) success=(?P<success>\d+) fail=(?P<fail>\d+) "
    r"callbackNs=(?P<callback_ns>\d+) callbackAvgNs=(?P<callback_avg_ns>\d+) "
    r"callbackMaxNs=(?P<callback_max_ns>\d+) badSize=(?P<bad_size>\d+) "
    r"s8=(?P<s8_n>\d+)/(?P<s8_ok>\d+)/(?P<s8_fail>\d+)/(?P<s8_ns>\d+) "
    r"s16=(?P<s16_n>\d+)/(?P<s16_ok>\d+)/(?P<s16_fail>\d+)/(?P<s16_ns>\d+) "
    r"s32=(?P<s32_n>\d+)/(?P<s32_ok>\d+)/(?P<s32_fail>\d+)/(?P<s32_ns>\d+) "
    r"s64=(?P<s64_n>\d+)/(?P<s64_ok>\d+)/(?P<s64_fail>\d+)/(?P<s64_ns>\d+) "
    r"s128=(?P<s128_n>\d+)/(?P<s128_ok>\d+)/(?P<s128_fail>\d+)/(?P<s128_ns>\d+)"
    r"(?: readAttempts=(?P<read_attempts>\d+) readNs=(?P<read_ns>\d+) "
    r"readAvgNs=(?P<read_avg_ns>\d+) readMaxNs=(?P<read_max_ns>\d+) "
    r"readBadSize=(?P<read_bad_size>\d+) "
    r"rs8=(?P<rs8_n>\d+)/(?P<rs8_ns>\d+) rs16=(?P<rs16_n>\d+)/(?P<rs16_ns>\d+) "
    r"rs32=(?P<rs32_n>\d+)/(?P<rs32_ns>\d+) rs64=(?P<rs64_n>\d+)/(?P<rs64_ns>\d+) "
    r"rs128=(?P<rs128_n>\d+)/(?P<rs128_ns>\d+))?"
)

DEFAULT_FAST = (960, 1080)
DEFAULT_SLOW = (1320, 1440, 1560)
SIZE_NAMES = ("8", "16", "32", "64", "128")


@dataclass(frozen=True)
class Window:
    frame: int
    producer: int
    attempts: int
    success: int
    failure: int
    callback_ns: int
    callback_avg_ns: int
    callback_max_ns: int
    bad_size: int
    size_attempts: tuple[int, ...]
    size_success: tuple[int, ...]
    size_failure: tuple[int, ...]
    size_ns: tuple[int, ...]
    read_attempts: int | None
    read_ns: int | None
    read_avg_ns: int | None
    read_max_ns: int | None
    read_bad_size: int | None
    read_size_attempts: tuple[int, ...] | None
    read_size_ns: tuple[int, ...] | None

    @property
    def failure_rate(self) -> float:
        return 0.0 if self.attempts == 0 else self.failure * 100.0 / self.attempts


def parse_frame_list(value: str) -> tuple[int, ...]:
    frames = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not frames:
        raise argparse.ArgumentTypeError("frame list must not be empty")
    return frames


def optional_int(match: re.Match[str], name: str) -> int | None:
    value = match.group(name)
    return None if value is None else int(value)


def parse_log(path: Path) -> list[Window]:
    windows: list[Window] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_RE.search(line)
        if not match:
            continue
        size_attempts = tuple(int(match.group(f"s{name}_n")) for name in SIZE_NAMES)
        size_success = tuple(int(match.group(f"s{name}_ok")) for name in SIZE_NAMES)
        size_failure = tuple(int(match.group(f"s{name}_fail")) for name in SIZE_NAMES)
        size_ns = tuple(int(match.group(f"s{name}_ns")) for name in SIZE_NAMES)
        has_read = match.group("read_attempts") is not None
        read_size_attempts = (
            tuple(int(match.group(f"rs{name}_n")) for name in SIZE_NAMES) if has_read else None
        )
        read_size_ns = (
            tuple(int(match.group(f"rs{name}_ns")) for name in SIZE_NAMES) if has_read else None
        )
        window = Window(
            frame=int(match.group("frame")),
            producer=int(match.group("producer")),
            attempts=int(match.group("attempts")),
            success=int(match.group("success")),
            failure=int(match.group("fail")),
            callback_ns=int(match.group("callback_ns")),
            callback_avg_ns=int(match.group("callback_avg_ns")),
            callback_max_ns=int(match.group("callback_max_ns")),
            bad_size=int(match.group("bad_size")),
            size_attempts=size_attempts,
            size_success=size_success,
            size_failure=size_failure,
            size_ns=size_ns,
            read_attempts=optional_int(match, "read_attempts"),
            read_ns=optional_int(match, "read_ns"),
            read_avg_ns=optional_int(match, "read_avg_ns"),
            read_max_ns=optional_int(match, "read_max_ns"),
            read_bad_size=optional_int(match, "read_bad_size"),
            read_size_attempts=read_size_attempts,
            read_size_ns=read_size_ns,
        )
        if window.success + window.failure != window.attempts:
            raise ValueError(f"frame {window.frame} producer {window.producer}: success+fail mismatch")
        if sum(size_attempts) + window.bad_size != window.attempts:
            raise ValueError(f"frame {window.frame} producer {window.producer}: write size accounting mismatch")
        if has_read:
            assert window.read_attempts is not None
            assert window.read_bad_size is not None
            assert window.read_size_attempts is not None
            if sum(window.read_size_attempts) + window.read_bad_size != window.read_attempts:
                raise ValueError(
                    f"frame {window.frame} producer {window.producer}: read size accounting mismatch"
                )
        windows.append(window)
    if not windows:
        raise ValueError("no [X1-XEXCL] records found")
    return windows


def ratio(slow: float, fast: float) -> str:
    if fast == 0.0:
        return "inf" if slow > 0.0 else "n/a"
    return f"{slow / fast:.3f}x"


def avg(total: int, count: int) -> float:
    return 0.0 if count == 0 else total / count


def aggregate_write(selected: list[Window]) -> dict[str, object]:
    attempts = sum(item.attempts for item in selected)
    failure = sum(item.failure for item in selected)
    callback_ns = sum(item.callback_ns for item in selected)
    return {
        "attempts": attempts,
        "failure": failure,
        "failure_rate": 0.0 if attempts == 0 else failure * 100.0 / attempts,
        "callback_ns": callback_ns,
        "callback_avg_ns": avg(callback_ns, attempts),
        "attempts_per_window": attempts / len(selected),
        "callback_ns_per_window": callback_ns / len(selected),
    }


def aggregate_read(selected: list[Window]) -> dict[str, float] | None:
    if not selected or any(item.read_attempts is None or item.read_ns is None for item in selected):
        return None
    attempts = sum(int(item.read_attempts) for item in selected)
    callback_ns = sum(int(item.read_ns) for item in selected)
    return {
        "attempts": float(attempts),
        "callback_ns": float(callback_ns),
        "callback_avg_ns": avg(callback_ns, attempts),
        "attempts_per_window": attempts / len(selected),
        "callback_ns_per_window": callback_ns / len(selected),
    }


def print_cadence_summary(windows: list[Window], fast_frames: tuple[int, ...], slow_frames: tuple[int, ...]) -> None:
    by_producer: dict[int, dict[int, Window]] = defaultdict(dict)
    for window in windows:
        by_producer[window.producer][window.frame] = window

    for producer in sorted(by_producer):
        fast_selected = [by_producer[producer][frame] for frame in fast_frames if frame in by_producer[producer]]
        slow_selected = [by_producer[producer][frame] for frame in slow_frames if frame in by_producer[producer]]
        if not fast_selected or not slow_selected:
            print(
                f"producer={producer} insufficient cadence windows "
                f"fast={len(fast_selected)}/{len(fast_frames)} slow={len(slow_selected)}/{len(slow_frames)}"
            )
            continue

        fast_w = aggregate_write(fast_selected)
        slow_w = aggregate_write(slow_selected)
        print(
            f"producer={producer} fastFrames={','.join(str(w.frame) for w in fast_selected)} "
            f"slowFrames={','.join(str(w.frame) for w in slow_selected)}"
        )
        print(
            f"  STXR attempts/window {fast_w['attempts_per_window']:.1f} -> {slow_w['attempts_per_window']:.1f} "
            f"ratio={ratio(float(slow_w['attempts_per_window']), float(fast_w['attempts_per_window']))}"
        )
        print(
            f"  STXR failRate {fast_w['failure_rate']:.3f}% -> {slow_w['failure_rate']:.3f}%"
        )
        print(
            f"  STXR callbackAvgNs {fast_w['callback_avg_ns']:.1f} -> {slow_w['callback_avg_ns']:.1f} "
            f"ratio={ratio(float(slow_w['callback_avg_ns']), float(fast_w['callback_avg_ns']))}"
        )
        print(
            f"  STXR callbackNs/window {fast_w['callback_ns_per_window']:.1f} -> {slow_w['callback_ns_per_window']:.1f} "
            f"ratio={ratio(float(slow_w['callback_ns_per_window']), float(fast_w['callback_ns_per_window']))}"
        )

        fast_r = aggregate_read(fast_selected)
        slow_r = aggregate_read(slow_selected)
        if fast_r is None or slow_r is None:
            print("  LDXR read attribution not present in all selected windows")
            continue
        print(
            f"  LDXR attempts/window {fast_r['attempts_per_window']:.1f} -> {slow_r['attempts_per_window']:.1f} "
            f"ratio={ratio(slow_r['attempts_per_window'], fast_r['attempts_per_window'])}"
        )
        print(
            f"  LDXR callbackAvgNs {fast_r['callback_avg_ns']:.1f} -> {slow_r['callback_avg_ns']:.1f} "
            f"ratio={ratio(slow_r['callback_avg_ns'], fast_r['callback_avg_ns'])}"
        )
        print(
            f"  LDXR callbackNs/window {fast_r['callback_ns_per_window']:.1f} -> {slow_r['callback_ns_per_window']:.1f} "
            f"ratio={ratio(slow_r['callback_ns_per_window'], fast_r['callback_ns_per_window'])}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze X1 ARM64 exclusive read/write attribution")
    parser.add_argument("log", type=Path)
    parser.add_argument("--fast", type=parse_frame_list, default=DEFAULT_FAST,
                        help="comma-separated fast cadence frame IDs")
    parser.add_argument("--slow", type=parse_frame_list, default=DEFAULT_SLOW,
                        help="comma-separated slow cadence frame IDs")
    args = parser.parse_args()

    windows = parse_log(args.log)
    for window in windows:
        read_text = ""
        if window.read_attempts is not None:
            read_text = (
                f" readAttempts={window.read_attempts} readNs={window.read_ns} "
                f"readAvgNs={window.read_avg_ns} readMaxNs={window.read_max_ns}"
            )
        print(
            f"frame={window.frame} producer={window.producer} attempts={window.attempts} "
            f"success={window.success} fail={window.failure} failRate={window.failure_rate:.3f}% "
            f"callbackNs={window.callback_ns} callbackAvgNs={window.callback_avg_ns} "
            f"callbackMaxNs={window.callback_max_ns}{read_text}"
        )
    print_cadence_summary(windows, args.fast, args.slow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
