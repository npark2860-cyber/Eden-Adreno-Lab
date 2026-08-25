// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>
#include <chrono>
#include <cstddef>

#include "common/common_types.h"

namespace Vulkan {

class AdrenoProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static AdrenoProfiler& Get();

    void Initialize(bool is_qualcomm_proprietary);

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    static TimePoint Now() noexcept {
        return Clock::now();
    }

    static u64 ElapsedNs(TimePoint start) noexcept {
        return static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start)
                .count());
    }

    void FrameEnd();
    void RecordRenderPassBegin(u32 image_count);
    void RecordRenderPassReuse();
    void RecordRenderPassEnd(u32 image_count);
    void RecordPostRenderPassImageBarriers(u32 image_count);
    void RecordDeferredClear();
    void RecordSubmit();
    void RecordFinishWait(u64 nanoseconds);
    void RecordWorkerWait(u64 nanoseconds);
    void RecordGraphicsPipelineBuild(u64 nanoseconds, bool success);
    void RecordComputePipelineBuild(u64 nanoseconds, bool success);
    void RecordDescriptorReservation(size_t entries, bool descriptor_buffer);
    void RecordDescriptorOverflow();
    void RecordDescriptorBufferBind();

private:
    AdrenoProfiler();

    static bool ParseEnabled();
    static u32 ParseReportFrames();

    struct Counters {
        std::atomic<u64> render_pass_begin{0};
        std::atomic<u64> render_pass_reuse{0};
        std::atomic<u64> render_pass_end{0};
        std::atomic<u64> render_pass_images{0};
        std::atomic<u64> post_render_pass_image_barriers{0};
        std::atomic<u64> deferred_clears{0};
        std::atomic<u64> submits{0};
        std::atomic<u64> finish_waits{0};
        std::atomic<u64> finish_wait_ns{0};
        std::atomic<u64> worker_waits{0};
        std::atomic<u64> worker_wait_ns{0};
        std::atomic<u64> graphics_pipeline_builds{0};
        std::atomic<u64> graphics_pipeline_failures{0};
        std::atomic<u64> graphics_pipeline_build_ns{0};
        std::atomic<u64> compute_pipeline_builds{0};
        std::atomic<u64> compute_pipeline_failures{0};
        std::atomic<u64> compute_pipeline_build_ns{0};
        std::atomic<u64> descriptor_reservations{0};
        std::atomic<u64> descriptor_entries{0};
        std::atomic<u64> descriptor_buffer_entries{0};
        std::atomic<u64> descriptor_overflows{0};
        std::atomic<u64> descriptor_buffer_binds{0};
    } counters;

    const bool requested;
    const u32 report_every_frames;
    std::atomic<bool> enabled{false};
    u64 frames_since_report{};
};

} // namespace Vulkan
