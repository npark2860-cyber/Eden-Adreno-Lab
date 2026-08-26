#!/usr/bin/env python3
"""Final safety pass for the exact dc95 X1 full-flow diagnostic checkout.

Run after:
  1. P0.2 non-scheduler patches
  2. descriptor/check-box/full-flow transplants
  3. exact dc95 scheduler-flow transplant

This pass intentionally does not import later Eden behavior. It only:
  - restores the exact dc95 Scheduler::Wait pacing policy around the profiler timer,
  - attributes actual async graphics/compute pipeline-ready blocking including mutex contention,
  - makes runtime sampler-workaround counters explicitly Qualcomm-only,
  - fixes the known dc95 Present-result instrumentation scope issue and shadow warning.

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

    # 2) Directly attribute all time blocked on asynchronous pipeline readiness.
    #    Start the timer before acquiring build_mutex, because the builder can hold
    #    that mutex while completing. The atomic pre-check does not change control flow.
    wait_block = '''        scheduler.Record([this](vk::CommandBuffer) {
            std::unique_lock lock{build_mutex};
            build_condvar.wait(lock, [this] { return is_built.load(std::memory_order::relaxed); });
        });
'''

    graphics = vulkan / "vk_graphics_pipeline.cpp"
    text = graphics.read_text(encoding="utf-8")
    graphics_wait = '''        scheduler.Record([this](vk::CommandBuffer) {
            auto& x1_wait_profiler = AdrenoProfiler::Get();
            const bool profile_wait = x1_wait_profiler.PipelineEnabled();
            const bool was_pending = !is_built.load(std::memory_order::relaxed);
            const auto wait_start = was_pending && profile_wait
                                        ? AdrenoProfiler::Now()
                                        : AdrenoProfiler::TimePoint{};
            std::unique_lock lock{build_mutex};
            build_condvar.wait(lock, [this] { return is_built.load(std::memory_order::relaxed); });
            if (was_pending && profile_wait) {
                x1_wait_profiler.RecordPipelineWait(false, AdrenoProfiler::ElapsedNs(wait_start));
            }
        });
'''
    text = replace_once(text, wait_block, graphics_wait, "graphics pipeline ready wait")
    graphics.write_text(text, encoding="utf-8")

    compute = vulkan / "vk_compute_pipeline.cpp"
    text = compute.read_text(encoding="utf-8")
    compute_wait = '''        scheduler.Record([this](vk::CommandBuffer) {
            auto& x1_wait_profiler = AdrenoProfiler::Get();
            const bool profile_wait = x1_wait_profiler.PipelineEnabled();
            const bool was_pending = !is_built.load(std::memory_order_relaxed);
            const auto wait_start = was_pending && profile_wait
                                        ? AdrenoProfiler::Now()
                                        : AdrenoProfiler::TimePoint{};
            std::unique_lock lock{build_mutex};
            build_condvar.wait(lock, [this] { return is_built.load(std::memory_order::relaxed); });
            if (was_pending && profile_wait) {
                x1_wait_profiler.RecordPipelineWait(true, AdrenoProfiler::ElapsedNs(wait_start));
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

    # 4) Fix the exact compile failure seen in the previous ARM64 attempt.
    #    The instrumentation hoists Present()'s VkResult out of the switch initializer,
    #    so both error branches must reference present_result. Also avoid shadowing
    #    AcquireNextImage()'s profiler variable inside its pacing lambda.
    swapchain = vulkan / "vk_swapchain.cpp"
    text = swapchain.read_text(encoding="utf-8")

    pacing_start_old = '''    auto& profiler = AdrenoProfiler::Get();
    const auto pacing_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()
                                                        : AdrenoProfiler::TimePoint{};
'''
    pacing_start_new = '''    auto& pacing_profiler = AdrenoProfiler::Get();
    const auto pacing_start = pacing_profiler.PresentEnabled() ? AdrenoProfiler::Now()
                                                               : AdrenoProfiler::TimePoint{};
'''
    text = replace_once(text, pacing_start_old, pacing_start_new, "swapchain pacing profiler name")

    pacing_end_old = '''    if (profiler.PresentEnabled()) {
        profiler.RecordPresentWait("swapchain-resource-pacing",
                                   AdrenoProfiler::ElapsedNs(pacing_start));
    }
'''
    pacing_end_new = '''    if (pacing_profiler.PresentEnabled()) {
        pacing_profiler.RecordPresentWait("swapchain-resource-pacing",
                                          AdrenoProfiler::ElapsedNs(pacing_start));
    }
'''
    text = replace_once(text, pacing_end_old, pacing_end_new, "swapchain pacing profiler use")

    present_switch_old = '''    switch (present_result) {
    case VK_SUCCESS:
        break;
    case VK_SUBOPTIMAL_KHR:
        LOG_DEBUG(Render_Vulkan, "Suboptimal swapchain");
        break;
    case VK_ERROR_OUT_OF_DATE_KHR:
        is_outdated = true;
        break;
    case VK_ERROR_SURFACE_LOST_KHR:
        vk::Check(result);
        break;
    default:
        LOG_CRITICAL(Render_Vulkan, "Failed to present with error {}", string_VkResult(result));
        break;
    }
'''
    present_switch_new = '''    switch (present_result) {
    case VK_SUCCESS:
        break;
    case VK_SUBOPTIMAL_KHR:
        LOG_DEBUG(Render_Vulkan, "Suboptimal swapchain");
        break;
    case VK_ERROR_OUT_OF_DATE_KHR:
        is_outdated = true;
        break;
    case VK_ERROR_SURFACE_LOST_KHR:
        vk::Check(present_result);
        break;
    default:
        LOG_CRITICAL(Render_Vulkan, "Failed to present with error {}",
                     string_VkResult(present_result));
        break;
    }
'''
    text = replace_once(text, present_switch_old, present_switch_new, "swapchain present result scope")
    swapchain.write_text(text, encoding="utf-8")

    # 5) Guard against known later scheduler behavior accidentally leaking into the
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

    print(
        "Finalized exact dc95 X1 full-flow diagnostic hooks: pacing preserved, "
        "pipeline waits attributed, swapchain scope fixed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
