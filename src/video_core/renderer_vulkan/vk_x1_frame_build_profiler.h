// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>
#include <chrono>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Vulkan {

// Observation-only wall-clock attribution for the CPU-side Vulkan frame-build path.
//
// The profiler is deliberately independent from the broader X1 flow profiler so it can be
// enabled while Scheduler/Present/Pipeline/Upload/QCOM heavy logging remains disabled.
// It never sleeps, waits, flushes, submits, changes guest state, or changes rendering policy.
class X1FrameBuildProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1FrameBuildProfiler& Get() {
        static X1FrameBuildProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        qcom_driver.store(is_qualcomm_proprietary, std::memory_order_relaxed);
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return qcom_driver.load(std::memory_order_relaxed) &&
               Settings::values.x1_frame_build_attribution_log.GetValue();
    }

    static TimePoint Now() noexcept {
        return Clock::now();
    }

    static u64 BetweenNs(TimePoint start, TimePoint end) noexcept {
        return static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count());
    }

    static u64 ElapsedNs(TimePoint start) noexcept {
        return BetweenNs(start, Clock::now());
    }

    void RecordPrepareDraw(u64 total_ns, u64 flush_ns, u64 memory_ns, u64 pre_config_ns,
                           u64 configure_ns, u64 post_config_ns) noexcept {
        if (!Enabled()) {
            return;
        }
        Add(counters.draw_calls, 1);
        Add(counters.draw_total_ns, total_ns);
        Add(counters.draw_flush_ns, flush_ns);
        Add(counters.draw_memory_ns, memory_ns);
        Add(counters.draw_pre_config_ns, pre_config_ns);
        Add(counters.draw_configure_ns, configure_ns);
        Add(counters.draw_post_config_ns, post_config_ns);
    }

    void RecordGraphicsConfigure(u64 total_ns, u64 sync_descriptors_ns, u64 stage_scan_ns,
                                 u64 fill_views_ns, u64 bind_views_ns, u64 update_buffers_ns,
                                 u64 descriptor_prepare_ns, u64 configure_draw_ns) noexcept {
        if (!Enabled()) {
            return;
        }
        Add(counters.gfx_config_calls, 1);
        Add(counters.gfx_config_total_ns, total_ns);
        Add(counters.gfx_sync_descriptors_ns, sync_descriptors_ns);
        Add(counters.gfx_stage_scan_ns, stage_scan_ns);
        Add(counters.gfx_fill_views_ns, fill_views_ns);
        Add(counters.gfx_bind_views_ns, bind_views_ns);
        Add(counters.gfx_update_buffers_ns, update_buffers_ns);
        Add(counters.gfx_descriptor_prepare_ns, descriptor_prepare_ns);
        Add(counters.gfx_configure_draw_ns, configure_draw_ns);
    }

    void RecordDispatch(u64 total_ns, u64 flush_ns, u64 memory_ns, u64 configure_ns,
                        u64 issue_ns) noexcept {
        if (!Enabled()) {
            return;
        }
        Add(counters.dispatch_calls, 1);
        Add(counters.dispatch_total_ns, total_ns);
        Add(counters.dispatch_flush_ns, flush_ns);
        Add(counters.dispatch_memory_ns, memory_ns);
        Add(counters.dispatch_configure_ns, configure_ns);
        Add(counters.dispatch_issue_ns, issue_ns);
    }

    void RecordDrawTexture(u64 total_ns) noexcept {
        if (Enabled()) {
            Add(counters.draw_texture_calls, 1);
            Add(counters.draw_texture_ns, total_ns);
        }
    }

    void RecordClear(u64 total_ns) noexcept {
        if (Enabled()) {
            Add(counters.clear_calls, 1);
            Add(counters.clear_ns, total_ns);
        }
    }

    void RecordFlushCommands(u64 total_ns) noexcept {
        if (Enabled()) {
            Add(counters.flush_commands_calls, 1);
            Add(counters.flush_commands_ns, total_ns);
        }
    }

    void RecordTickFrame(u64 total_ns) noexcept {
        if (Enabled()) {
            Add(counters.tick_frame_ns, total_ns);
        }
    }

    void FrameEnd() {
        if (!Enabled()) {
            return;
        }

        const u64 frame = frame_id.fetch_add(1, std::memory_order_relaxed) + 1;
        ++frames_since_report;
        if (frames_since_report < ReportFrames) {
            return;
        }
        const u64 frames = frames_since_report;
        frames_since_report = 0;

        const u64 draw_calls = Take(counters.draw_calls);
        const u64 draw_total_ns = Take(counters.draw_total_ns);
        const u64 draw_flush_ns = Take(counters.draw_flush_ns);
        const u64 draw_memory_ns = Take(counters.draw_memory_ns);
        const u64 draw_pre_config_ns = Take(counters.draw_pre_config_ns);
        const u64 draw_configure_ns = Take(counters.draw_configure_ns);
        const u64 draw_post_config_ns = Take(counters.draw_post_config_ns);

        const u64 gfx_config_calls = Take(counters.gfx_config_calls);
        const u64 gfx_config_total_ns = Take(counters.gfx_config_total_ns);
        const u64 gfx_sync_descriptors_ns = Take(counters.gfx_sync_descriptors_ns);
        const u64 gfx_stage_scan_ns = Take(counters.gfx_stage_scan_ns);
        const u64 gfx_fill_views_ns = Take(counters.gfx_fill_views_ns);
        const u64 gfx_bind_views_ns = Take(counters.gfx_bind_views_ns);
        const u64 gfx_update_buffers_ns = Take(counters.gfx_update_buffers_ns);
        const u64 gfx_descriptor_prepare_ns = Take(counters.gfx_descriptor_prepare_ns);
        const u64 gfx_configure_draw_ns = Take(counters.gfx_configure_draw_ns);

        const u64 dispatch_calls = Take(counters.dispatch_calls);
        const u64 dispatch_total_ns = Take(counters.dispatch_total_ns);
        const u64 dispatch_flush_ns = Take(counters.dispatch_flush_ns);
        const u64 dispatch_memory_ns = Take(counters.dispatch_memory_ns);
        const u64 dispatch_configure_ns = Take(counters.dispatch_configure_ns);
        const u64 dispatch_issue_ns = Take(counters.dispatch_issue_ns);

        const u64 draw_texture_calls = Take(counters.draw_texture_calls);
        const u64 draw_texture_ns = Take(counters.draw_texture_ns);
        const u64 clear_calls = Take(counters.clear_calls);
        const u64 clear_ns = Take(counters.clear_ns);
        const u64 flush_commands_calls = Take(counters.flush_commands_calls);
        const u64 flush_commands_ns = Take(counters.flush_commands_ns);
        const u64 tick_frame_ns = Take(counters.tick_frame_ns);

        LOG_INFO(Render_Vulkan,
                 "[X1-FRAMEBUILD] frame={} frames={} "
                 "drawCalls={} draw={:.3f}ms flush={:.3f}ms mem={:.3f}ms preCfg={:.3f}ms cfg={:.3f}ms post={:.3f}ms "
                 "gfxCfgCalls={} gfxCfg={:.3f}ms syncDesc={:.3f}ms stageScan={:.3f}ms fillViews={:.3f}ms bindViews={:.3f}ms buffers={:.3f}ms descPrep={:.3f}ms cfgDraw={:.3f}ms "
                 "dispatchCalls={} dispatch={:.3f}ms dFlush={:.3f}ms dMem={:.3f}ms dCfg={:.3f}ms dIssue={:.3f}ms "
                 "drawTextureCalls={} drawTexture={:.3f}ms clearCalls={} clear={:.3f}ms flushCmdCalls={} flushCmd={:.3f}ms tick={:.3f}ms",
                 frame, frames, draw_calls, ToMs(draw_total_ns), ToMs(draw_flush_ns),
                 ToMs(draw_memory_ns), ToMs(draw_pre_config_ns), ToMs(draw_configure_ns),
                 ToMs(draw_post_config_ns), gfx_config_calls, ToMs(gfx_config_total_ns),
                 ToMs(gfx_sync_descriptors_ns), ToMs(gfx_stage_scan_ns), ToMs(gfx_fill_views_ns),
                 ToMs(gfx_bind_views_ns), ToMs(gfx_update_buffers_ns),
                 ToMs(gfx_descriptor_prepare_ns), ToMs(gfx_configure_draw_ns), dispatch_calls,
                 ToMs(dispatch_total_ns), ToMs(dispatch_flush_ns), ToMs(dispatch_memory_ns),
                 ToMs(dispatch_configure_ns), ToMs(dispatch_issue_ns), draw_texture_calls,
                 ToMs(draw_texture_ns), clear_calls, ToMs(clear_ns), flush_commands_calls,
                 ToMs(flush_commands_ns), ToMs(tick_frame_ns));
    }

private:
    static constexpr u64 ReportFrames = 120;

    static void Add(std::atomic<u64>& dst, u64 value) noexcept {
        dst.fetch_add(value, std::memory_order_relaxed);
    }

    static u64 Take(std::atomic<u64>& value) noexcept {
        return value.exchange(0, std::memory_order_relaxed);
    }

    static double ToMs(u64 ns) noexcept {
        return static_cast<double>(ns) / 1'000'000.0;
    }

    struct Counters {
        std::atomic<u64> draw_calls{0};
        std::atomic<u64> draw_total_ns{0};
        std::atomic<u64> draw_flush_ns{0};
        std::atomic<u64> draw_memory_ns{0};
        std::atomic<u64> draw_pre_config_ns{0};
        std::atomic<u64> draw_configure_ns{0};
        std::atomic<u64> draw_post_config_ns{0};

        std::atomic<u64> gfx_config_calls{0};
        std::atomic<u64> gfx_config_total_ns{0};
        std::atomic<u64> gfx_sync_descriptors_ns{0};
        std::atomic<u64> gfx_stage_scan_ns{0};
        std::atomic<u64> gfx_fill_views_ns{0};
        std::atomic<u64> gfx_bind_views_ns{0};
        std::atomic<u64> gfx_update_buffers_ns{0};
        std::atomic<u64> gfx_descriptor_prepare_ns{0};
        std::atomic<u64> gfx_configure_draw_ns{0};

        std::atomic<u64> dispatch_calls{0};
        std::atomic<u64> dispatch_total_ns{0};
        std::atomic<u64> dispatch_flush_ns{0};
        std::atomic<u64> dispatch_memory_ns{0};
        std::atomic<u64> dispatch_configure_ns{0};
        std::atomic<u64> dispatch_issue_ns{0};

        std::atomic<u64> draw_texture_calls{0};
        std::atomic<u64> draw_texture_ns{0};
        std::atomic<u64> clear_calls{0};
        std::atomic<u64> clear_ns{0};
        std::atomic<u64> flush_commands_calls{0};
        std::atomic<u64> flush_commands_ns{0};
        std::atomic<u64> tick_frame_ns{0};
    } counters;

    std::atomic<bool> qcom_driver{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
};

} // namespace Vulkan
