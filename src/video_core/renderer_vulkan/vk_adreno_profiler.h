// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>

#include "common/common_types.h"

namespace Vulkan {

enum class RenderPassEndReason : u8 {
    Unknown,
    DeferredClear,
    FramebufferChange,
    OutsideOperation,
    Submit,
    FlushDeferredClear,
};

class AdrenoProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    enum class QcomEvent : u32 {
        DescriptorTilerPolicy = 0,
        DynamicStorageLimit,
        ShaderProfile,
        CustomBorderColor,
        BorderColorSwizzle,
        Count,
    };

    static AdrenoProfiler& Get();

    void Initialize(bool is_qualcomm_proprietary);

    [[nodiscard]] bool Enabled() const noexcept;
    [[nodiscard]] bool SchedulerEnabled() const noexcept;
    [[nodiscard]] bool PresentEnabled() const noexcept;
    [[nodiscard]] bool PipelineEnabled() const noexcept;
    [[nodiscard]] bool UploadEnabled() const noexcept;
    [[nodiscard]] bool QcomEnabled() const noexcept;
    [[nodiscard]] bool DescriptorEnabled() const noexcept;

    [[nodiscard]] u64 CurrentFrame() const noexcept {
        return frame_id.load(std::memory_order_relaxed);
    }

    static TimePoint Now() noexcept {
        return Clock::now();
    }

    static u64 ElapsedNs(TimePoint start) noexcept {
        return static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count());
    }

    void FrameEnd();

    // Broad P0/P0.2 API retained for the compile-validated hooks.
    void RecordRenderPassBegin(u32 image_count);
    void RecordRenderPassReuse();
    void RecordRenderPassEnd(u32 image_count, RenderPassEndReason reason);
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
    void RecordStagingRequest(u64 bytes, bool download, bool deferred);
    void RecordBufferCopy(u64 bytes, bool reordered_upload);

    // Full-flow additions.
    void RecordSchedulerWait(u64 tick, bool forced_flush, u64 gpu_wait_ns, u64 pacing_wait_ns);
    void RecordPresentWait(const char* reason, u64 nanoseconds);
    void RecordAcquire(u64 nanoseconds, int result);
    void RecordPresentCall(u64 nanoseconds, int result);
    void RecordShaderEmit(const char* kind, u64 nanoseconds, u64 bytes);
    void RecordPipelineWait(bool compute, u64 nanoseconds);
    void RecordBarrier(const char* reason, u64 count);
    void RecordQcomHit(QcomEvent event);
    void RecordDescriptorStall(const char* reason, u64 tick, u64 nanoseconds);

private:
    AdrenoProfiler();

    static u32 ParseReportFrames();
    static u64 ParseSlowEventNs();
    [[nodiscard]] bool AnyDiagnosticEnabled() const noexcept;
    void LogSlow(const char* category, const char* reason, u64 nanoseconds, u64 tick = 0,
                 u64 aux = 0) const;

    struct Counters {
        std::atomic<u64> render_pass_begin{0};
        std::atomic<u64> render_pass_reuse{0};
        std::atomic<u64> render_pass_end{0};
        std::atomic<u64> render_pass_images{0};
        std::atomic<u64> render_pass_end_unknown{0};
        std::atomic<u64> render_pass_end_deferred_clear{0};
        std::atomic<u64> render_pass_end_framebuffer_change{0};
        std::atomic<u64> render_pass_end_outside_operation{0};
        std::atomic<u64> render_pass_end_submit{0};
        std::atomic<u64> render_pass_end_flush_deferred_clear{0};
        std::atomic<u64> post_render_pass_image_barriers{0};
        std::atomic<u64> deferred_clears{0};
        std::atomic<u64> submits{0};
        std::atomic<u64> finish_waits{0};
        std::atomic<u64> finish_wait_ns{0};
        std::atomic<u64> worker_waits{0};
        std::atomic<u64> worker_wait_ns{0};
        std::atomic<u64> scheduler_waits{0};
        std::atomic<u64> scheduler_wait_ns{0};
        std::atomic<u64> scheduler_gpu_wait_ns{0};
        std::atomic<u64> scheduler_pacing_wait_ns{0};
        std::atomic<u64> scheduler_forced_flushes{0};

        std::atomic<u64> graphics_pipeline_builds{0};
        std::atomic<u64> graphics_pipeline_failures{0};
        std::atomic<u64> graphics_pipeline_build_ns{0};
        std::atomic<u64> graphics_pipeline_waits{0};
        std::atomic<u64> graphics_pipeline_wait_ns{0};
        std::atomic<u64> compute_pipeline_builds{0};
        std::atomic<u64> compute_pipeline_failures{0};
        std::atomic<u64> compute_pipeline_build_ns{0};
        std::atomic<u64> compute_pipeline_waits{0};
        std::atomic<u64> compute_pipeline_wait_ns{0};
        std::atomic<u64> shader_emits{0};
        std::atomic<u64> shader_emit_ns{0};
        std::atomic<u64> shader_bytes{0};

        std::atomic<u64> descriptor_reservations{0};
        std::atomic<u64> descriptor_entries{0};
        std::atomic<u64> descriptor_buffer_entries{0};
        std::atomic<u64> descriptor_overflows{0};
        std::atomic<u64> descriptor_buffer_binds{0};

        std::atomic<u64> staging_upload_requests{0};
        std::atomic<u64> staging_upload_bytes{0};
        std::atomic<u64> staging_download_requests{0};
        std::atomic<u64> staging_download_bytes{0};
        std::atomic<u64> staging_deferred_download_requests{0};
        std::atomic<u64> staging_deferred_download_bytes{0};
        std::atomic<u64> buffer_copy_calls{0};
        std::atomic<u64> buffer_copy_bytes{0};
        std::atomic<u64> reordered_upload_copy_calls{0};
        std::atomic<u64> reordered_upload_copy_bytes{0};
        std::atomic<u64> barriers{0};

        std::atomic<u64> present_waits{0};
        std::atomic<u64> present_wait_ns{0};
        std::atomic<u64> acquires{0};
        std::atomic<u64> acquire_ns{0};
        std::atomic<u64> acquire_failures{0};
        std::atomic<u64> presents{0};
        std::atomic<u64> present_ns{0};
        std::atomic<u64> present_failures{0};

        std::array<std::atomic<u64>, static_cast<size_t>(QcomEvent::Count)> qcom{};
    } counters;

    const u32 report_every_frames;
    const u64 slow_event_ns;
    std::atomic<bool> qcom_driver{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
};

} // namespace Vulkan
