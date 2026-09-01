#!/usr/bin/env python3
# Analyze selected-producer ARM64 exclusive-write/STXR attribution windows.

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

    @property
    def failure_rate(self) -> float:
        return 0.0 if self.attempts == 0 else self.failure * 100.0 / self.attempts


def parse_frame_list(value: str) -> tuple[int, ...]:
    frames = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not frames:
        raise argparse.ArgumentTypeError("frame list must not be empty")
    return frames


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
        )
        if window.success + window.failure != window.attempts:
            raise ValueError(f"frame {window.frame} producer {window.producer}: success+fail mismatch")
        if sum(size_attempts) + window.bad_size != window.attempts:
            raise ValueError(f"frame {window.frame} producer {window.producer}: size accounting mismatch")
        windows.append(window)
    if not windows:
        raise ValueError("no [X1-XEXCL] records found")
    return windows


def aggregate(selected: list[Window]) -> dict[str, object]:
    attempts = sum(item.attempts for item in selected)
    success = sum(item.success for item in selected)
    failure = sum(item.failure for item in selected)
    callback_ns = sum(item.callback_ns for item in selected)
    size_attempts = tuple(sum(item.size_attempts[i] for item in selected) for i in range(5))
    size_success = tuple(sum(item.size_success[i] for item in selected) for i in range(5))
    size_failure = tuple(sum(item.size_failure[i] for item in selected) for i in range(5))
    size_ns = tuple(sum(item.size_ns[i] for item in selected) for i in range(5))
    return {
        "windows": len(selected),
        "attempts": attempts,
        "success": success,
        "failure": failure,
        "failure_rate": 0.0 if attempts == 0 else failure * 100.0 / attempts,
        "callback_ns": callback_ns,
        "callback_avg_ns": 0.0 if attempts == 0 else callback_ns / attempts,
        "attempts_per_window": 0.0 if not selected else attempts / len(selected),
        "callback_ns_per_window": 0.0 if not selected else callback_ns / len(selected),
        "size_attempts": size_attempts,
        "size_success": size_success,
        "size_failure": size_failure,
        "size_ns": size_ns,
    }


def ratio(slow: float, fast: float) -> str:
    if fast == 0.0:
        return "inf" if slow > 0.0 else "n/a"
    return f"{slow / fast:.3f}x"


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

        fast = aggregate(fast_selected)
        slow = aggregate(slow_selected)
        print(
            f"producer={producer} fastFrames={','.join(str(w.frame) for w in fast_selected)} "
            f"slowFrames={','.join(str(w.frame) for w in slow_selected)}"
        )
        print(
            f"  attempts/window {fast['attempts_per_window']:.1f} -> {slow['attempts_per_window']:.1f} "
            f"ratio={ratio(float(slow['attempts_per_window']), float(fast['attempts_per_window']))}"
        )
        print(
            f"  failRate {fast['failure_rate']:.3f}% -> {slow['failure_rate']:.3f}% "
            f"failures {fast['failure']} -> {slow['failure']}"
        )
        print(
            f"  callbackAvgNs {fast['callback_avg_ns']:.1f} -> {slow['callback_avg_ns']:.1f} "
            f"ratio={ratio(float(slow['callback_avg_ns']), float(fast['callback_avg_ns']))}"
        )
        print(
            f"  callbackNs/window {fast['callback_ns_per_window']:.1f} -> {slow['callback_ns_per_window']:.1f} "
            f"ratio={ratio(float(slow['callback_ns_per_window']), float(fast['callback_ns_per_window']))}"
        )

        fast_size_attempts = fast["size_attempts"]
        slow_size_attempts = slow["size_attempts"]
        fast_size_fail = fast["size_failure"]
        slow_size_fail = slow["size_failure"]
        fast_size_ns = fast["size_ns"]
        slow_size_ns = slow["size_ns"]
        for index, name in enumerate(SIZE_NAMES):
            f_n = int(fast_size_attempts[index])
            s_n = int(slow_size_attempts[index])
            if f_n == 0 and s_n == 0:
                continue
            f_fail = int(fast_size_fail[index])
            s_fail = int(slow_size_fail[index])
            f_ns = int(fast_size_ns[index])
            s_ns = int(slow_size_ns[index])
            f_avg = 0.0 if f_n == 0 else f_ns / f_n
            s_avg = 0.0 if s_n == 0 else s_ns / s_n
            f_fail_rate = 0.0 if f_n == 0 else f_fail * 100.0 / f_n
            s_fail_rate = 0.0 if s_n == 0 else s_fail * 100.0 / s_n
            print(
                f"  size={name} attempts={f_n}->{s_n} failRate={f_fail_rate:.3f}%->{s_fail_rate:.3f}% "
                f"avgNs={f_avg:.1f}->{s_avg:.1f} avgRatio={ratio(s_avg, f_avg)}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze X1 ARM64 exclusive callback attribution")
    parser.add_argument("log", type=Path)
    parser.add_argument("--fast", type=parse_frame_list, default=DEFAULT_FAST,
                        help="comma-separated fast cadence frame IDs")
    parser.add_argument("--slow", type=parse_frame_list, default=DEFAULT_SLOW,
                        help="comma-separated slow cadence frame IDs")
    args = parser.parse_args()

    windows = parse_log(args.log)
    for window in windows:
        print(
            f"frame={window.frame} producer={window.producer} attempts={window.attempts} "
            f"success={window.success} fail={window.failure} failRate={window.failure_rate:.3f}% "
            f"callbackNs={window.callback_ns} callbackAvgNs={window.callback_avg_ns} "
            f"callbackMaxNs={window.callback_max_ns}"
        )
    print_cadence_summary(windows, args.fast, args.slow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
