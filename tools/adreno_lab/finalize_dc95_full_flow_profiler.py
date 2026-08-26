#!/usr/bin/env python3
"""Final safety pass for the exact dc95 X1 full-flow diagnostic checkout.

Run after:
  1. P0.2 non-scheduler patches
  2. descriptor/check-box/full-flow transplants
  3. exact dc95 scheduler-flow transplant

This pass intentionally does not import later Eden behavior. It only:
  - restores the exact dc95 Scheduler::Wait pacing policy around the profiler timer,
  - attributes actual async graphics/compute pipeline-ready blocking,
  - makes runtime sampler-workaround counters explicitly Qualcomm-only.

Every edit is a strict single-anchor replacement. A source drift therefore fails
before compilation instead of silently producing a partially instrumented build.
"""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: finalize_dc95_full_flow_profiler.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # 1) Preserve exact dc95 frame-pacing behavior. The profiler measures around
    #    the original policy; it must not substitute the later 1 ms spin-tail policy.
    scheduler_h = vulkan / "vk_scheduler.h"
    text = scheduler_h.read_text(encoding="utf-8")
    old_pacing = '''            if (target_time >= now) {
                constexpr auto spin_tail = std::chrono::milliseconds(1);
                auto sleep_time = target_time - now;
                if (sleep_time > spin_tail * 2) {
                    std::this_thread::sleep_for(sleep_time - spin_tail);
                }
                while (std::chrono::steady_clock::now() < target_time) {
                    std::this_thread::yield();
                }
            } else if (frame_counter > max_frame_count) {
'''
    dc95_pacing = '''            if (target_time >= now) {
                auto sleep_time = target_time - now;
                if (sleep_time > std::chrono::milliseconds(15)) {
                    std::this_thread::sleep_for(sleep_time - std::chrono::milliseconds(1));
                }
                while (std::chrono::steady_clock::now() < target_time) {
                    std::this_thread::yield();
                }
            } else if (frame_counter > max_frame_count) {
'''
    text = replace_once(text, old_pacing, dc95_pacing, "restore exact dc95 pacing")
    if "spin_tail" in text:
        raise RuntimeError("scheduler pacing finalizer: later spin_tail policy still present")
    scheduler_h.write_text(text, encoding="utf-8")

    # 2) Directly attribute time spent blocked for asynchronous pipeline readiness.
    #    The pending flag is read while holding the same mutex used by the builder;
    #    only a genuinely pending condvar wait is counted. Control flow is unchanged.
    wait_block = '''        scheduler.Record([this](vk::CommandBuffer) {
            std::unique_lock lock{build_mutex};
            build_condvar.wait(lock, [this] { return is_built.load(std::memory_order::relaxed); });
        });
'''

    graphics = vulkan / "vk_graphics_pipeline.cpp"
    text = graphics.read_text(encoding="utf-8")
    graphics_wait = '''        scheduler.Record([this](vk::CommandBuffer) {
            auto& profiler = AdrenoProfiler::Get();
            std::unique_lock lock{build_mutex};
            const bool pending = !is_built.load(std::memory_order::relaxed);
            const auto wait_start = pending && profiler.PipelineEnabled()
                                        ? AdrenoProfiler::Now()
                                        : AdrenoProfiler::TimePoint{};
            build_condvar.wait(lock, [this] { return is_built.load(std::memory_order::relaxed); });
            if (pending && profiler.PipelineEnabled()) {
                profiler.RecordPipelineWait(false, AdrenoProfiler::ElapsedNs(wait_start));
            }
        });
'''
    text = replace_once(text, wait_block, graphics_wait, "graphics pipeline ready wait")
    graphics.write_text(text, encoding="utf-8")

    compute = vulkan / "vk_compute_pipeline.cpp"
    text = compute.read_text(encoding="utf-8")
    compute_wait = '''        scheduler.Record([this](vk::CommandBuffer) {
            auto& profiler = AdrenoProfiler::Get();
            std::unique_lock lock{build_mutex};
            const bool pending = !is_built.load(std::memory_order_relaxed);
            const auto wait_start = pending && profiler.PipelineEnabled()
                                        ? AdrenoProfiler::Now()
                                        : AdrenoProfiler::TimePoint{};
            build_condvar.wait(lock, [this] { return is_built.load(std::memory_order_relaxed); });
            if (pending && profiler.PipelineEnabled()) {
                profiler.RecordPipelineWait(true, AdrenoProfiler::ElapsedNs(wait_start));
            }
        });
'''
    text = replace_once(text, wait_block, compute_wait, "compute pipeline ready wait")
    compute.write_text(text, encoding="utf-8")

    # 3) Record sampler workaround hits only when the actual driver is Qualcomm.
    #    Other constructor-time QCOM hooks already carry explicit driver checks.
    texture = vulkan / "vk_texture_cache.cpp"
    text = texture.read_text(encoding="utf-8")
    old_custom = '''    if (has_custom_border_colors) {
        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::CustomBorderColor);
        pnext = &border_ci;
'''
    new_custom = '''    if (has_custom_border_colors) {
        if (device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY) {
            AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::CustomBorderColor);
        }
        pnext = &border_ci;
'''
    text = replace_once(text, old_custom, new_custom, "QCOM custom-border gating")

    old_swizzle = '''    if (device.IsExtBorderColorSwizzleSupported()) {
        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::BorderColorSwizzle);
    }
'''
    new_swizzle = '''    if (device.IsExtBorderColorSwizzleSupported() &&
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY) {
        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::BorderColorSwizzle);
    }
'''
    text = replace_once(text, old_swizzle, new_swizzle, "QCOM border-swizzle gating")
    texture.write_text(text, encoding="utf-8")

    # 4) Guard against known later scheduler behavior accidentally leaking into the
    #    exact dc95 diagnostic branch.
    scheduler_cpp = (vulkan / "vk_scheduler.cpp").read_text(encoding="utf-8")
    forbidden = {
        "MarkResolveShadowsUpToDate": "later resolve-shadow behavior",
        "FlushDeferredClear()": "later deferred-clear behavior",
        "depth_stencil_discard": "later render-pass variant behavior",
    }
    for token, label in forbidden.items():
        if token in scheduler_cpp:
            raise RuntimeError(f"exact dc95 guard failed: found {label}: {token}")

    print("Finalized exact dc95 X1 full-flow diagnostic hooks without behavioral pacing changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
