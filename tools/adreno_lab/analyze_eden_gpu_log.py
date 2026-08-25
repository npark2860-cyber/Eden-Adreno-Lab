#!/usr/bin/env python3
"""Summarize Eden GPU/Vulkan logs for Adreno lab baseline work.

This tool is intentionally read-only: it extracts counters and coarse timing from
Eden's existing logging without changing renderer behaviour.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

TIMESTAMP = re.compile(r"^\[\s*(?P<ts>[0-9]+(?:\.[0-9]+)?)\]")
RENDERPASS_BEGIN = re.compile(r"\[RenderPass\] Begin: .*?numImages=(?P<images>\d+)")
RENDERPASS_END = re.compile(r"\[RenderPass\] End")
VULKAN_CALL = re.compile(r"\[Vulkan\].*?\s(?P<call>vk[A-Za-z0-9_]+)\(")
PIPELINE_STATE = re.compile(r"\[Pipeline\] State change: (?P<state>.+)$")
PIPELINE_BIND = re.compile(r"\[Pipeline\] Bind (?P<type>Graphics|Compute) pipeline:")
DESCRIPTOR_BIND = re.compile(r"\[Descriptor\] Bind:")
MEM_ALLOC = re.compile(r"\[Memory\] Allocated (?P<size>[0-9.]+) (?P<unit>B|KB|MB|GB) .*?\(Device:(?P<device>Yes|No), Host:(?P<host>Yes|No)\)")
MEM_FREE = re.compile(r"\[Memory\] Deallocated (?P<size>[0-9.]+) (?P<unit>B|KB|MB|GB)")
GRAPHICS_FAIL = re.compile(r"Graphics pipeline build failed")
COMPUTE_FAIL = re.compile(r"Adreno rejected compute shader")

UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}


def bytes_from_match(match: re.Match[str]) -> int:
    return int(float(match.group("size")) * UNITS[match.group("unit")])


def parse(path: Path) -> dict:
    calls: Counter[str] = Counter()
    pipeline_states: Counter[str] = Counter()
    rp_begin = rp_end = rp_images = 0
    gfx_binds = compute_binds = descriptor_binds = 0
    gfx_failures = compute_failures = 0
    alloc_count = free_count = 0
    alloc_bytes = free_bytes = 0
    device_local_allocs = host_visible_allocs = dual_visible_allocs = 0
    first_ts = last_ts = None
    lines = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            lines += 1
            line = raw.rstrip("\n")

            ts = TIMESTAMP.match(line)
            if ts:
                value = float(ts.group("ts"))
                first_ts = value if first_ts is None else first_ts
                last_ts = value

            match = RENDERPASS_BEGIN.search(line)
            if match:
                rp_begin += 1
                rp_images += int(match.group("images"))
            if RENDERPASS_END.search(line):
                rp_end += 1

            match = VULKAN_CALL.search(line)
            if match:
                calls[match.group("call")] += 1

            match = PIPELINE_STATE.search(line)
            if match:
                pipeline_states[match.group("state").strip()] += 1

            match = PIPELINE_BIND.search(line)
            if match:
                if match.group("type") == "Graphics":
                    gfx_binds += 1
                else:
                    compute_binds += 1

            if DESCRIPTOR_BIND.search(line):
                descriptor_binds += 1
            if GRAPHICS_FAIL.search(line):
                gfx_failures += 1
            if COMPUTE_FAIL.search(line):
                compute_failures += 1

            match = MEM_ALLOC.search(line)
            if match:
                alloc_count += 1
                alloc_bytes += bytes_from_match(match)
                device = match.group("device") == "Yes"
                host = match.group("host") == "Yes"
                device_local_allocs += int(device)
                host_visible_allocs += int(host)
                dual_visible_allocs += int(device and host)

            match = MEM_FREE.search(line)
            if match:
                free_count += 1
                free_bytes += bytes_from_match(match)

    duration = None
    if first_ts is not None and last_ts is not None and last_ts >= first_ts:
        duration = last_ts - first_ts

    queue_submits = calls.get("vkQueueSubmit", 0) + calls.get("vkQueueSubmit2", 0)
    pipeline_creates = sum(
        count for name, count in calls.items()
        if name in {"vkCreateGraphicsPipelines", "vkCreateComputePipelines"}
    )

    return {
        "file": str(path),
        "lines": lines,
        "logged_duration_seconds": duration,
        "render_pass": {
            "begin": rp_begin,
            "end": rp_end,
            "attachment_images_on_begin": rp_images,
            "begin_end_delta": rp_begin - rp_end,
        },
        "submission": {
            "queue_submit_calls": queue_submits,
            "vkQueueSubmit": calls.get("vkQueueSubmit", 0),
            "vkQueueSubmit2": calls.get("vkQueueSubmit2", 0),
        },
        "pipeline": {
            "create_calls": pipeline_creates,
            "graphics_binds": gfx_binds,
            "compute_binds": compute_binds,
            "graphics_build_failures": gfx_failures,
            "compute_build_failures": compute_failures,
            "state_changes": dict(pipeline_states.most_common(20)),
        },
        "descriptor": {"logged_binds": descriptor_binds},
        "memory": {
            "allocations": alloc_count,
            "deallocations": free_count,
            "allocated_bytes_logged": alloc_bytes,
            "deallocated_bytes_logged": free_bytes,
            "device_local_allocations": device_local_allocs,
            "host_visible_allocations": host_visible_allocs,
            "device_local_and_host_visible_allocations": dual_visible_allocs,
        },
        "top_vulkan_calls": calls.most_common(25),
    }


def print_text(data: dict) -> None:
    rp = data["render_pass"]
    submit = data["submission"]
    pipe = data["pipeline"]
    mem = data["memory"]
    duration = data["logged_duration_seconds"]

    print("=== Eden Adreno P0 log baseline ===")
    print(f"file: {data['file']}")
    if duration is not None:
        print(f"logged span: {duration:.3f}s")
    print(f"render pass: begin={rp['begin']} end={rp['end']} attachment-images={rp['attachment_images_on_begin']}")
    print(f"queue submits: {submit['queue_submit_calls']} (submit={submit['vkQueueSubmit']}, submit2={submit['vkQueueSubmit2']})")
    print(
        "pipeline: "
        f"create-calls={pipe['create_calls']} gfx-binds={pipe['graphics_binds']} "
        f"compute-binds={pipe['compute_binds']} gfx-fail={pipe['graphics_build_failures']} "
        f"compute-fail={pipe['compute_build_failures']}"
    )
    print(f"descriptor binds logged: {data['descriptor']['logged_binds']}")
    print(
        "memory: "
        f"alloc={mem['allocations']} free={mem['deallocations']} "
        f"device-local={mem['device_local_allocations']} host-visible={mem['host_visible_allocations']} "
        f"dual-visible={mem['device_local_and_host_visible_allocations']}"
    )
    if data["top_vulkan_calls"]:
        print("top Vulkan calls:")
        for name, count in data["top_vulkan_calls"]:
            print(f"  {name}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Eden main log or eden_gpu.log")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    result = parse(args.log)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_text(result)
