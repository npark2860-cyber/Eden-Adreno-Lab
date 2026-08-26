// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "video_core/renderer_vulkan/vk_adreno_profiler.h"

#include <algorithm>
#include <cstdlib>
#include <functional>
#include <thread>

#include "common/logging.h"
#include "common/settings.h"

namespace Vulkan {
namespace {

u64 Take(std::atomic<u64>& value) {
    return value.exchange(0, std::memory_order_relaxed);
}

double PerFrame(u64 value, u64 frames) {
    return frames == 0 ? 0.0 : static_cast<double>(value) / static_cast<double>(frames);
}

double ToMs(u64 nanoseconds) {
    return static_cast<double>(nanoseconds) / 1'000'000.0;
}

double ToMiB(u64 bytes) {
    return static_cast<double>(bytes) / (1024.0 * 1024.0);
}

u32 ThreadId() {
    return static_cast<u32>(std::hash<std::thread::id>{}(std::this_thread::get_id()));
}

} // Anonymous namespace

AdrenoProfiler& AdrenoProfiler::Get() {
    static AdrenoProfiler profiler;
    return profiler;
}

AdrenoProfiler::AdrenoProfiler()
    : report_every_frames{ParseReportFrames()}, slow_event_ns{ParseSlowEventNs()} {}

u32 AdrenoProfiler::ParseReportFrames() {
    const char* const raw = std::getenv("EDEN_X1_FLOW_PROFILE_FRAMES");
    if (!raw) {
        return 120;
    }
    char* end{};
    const unsigned long parsed = std::strtoul(raw, &end, 10);
    if (end == raw || *end != '\0') {
        return 120;
    }
    return static_cast<u32>(std::clamp(parsed, 1UL, 3600UL));
}

u64 AdrenoProfiler::ParseSlowEventNs() {
    const char* const raw = std::getenv("EDEN_X1_FLOW_SLOW_US");
    if (!raw) {
        return 1'000'000ULL;
    }
    char* end{};
    const unsigned long parsed = std::strtoul(raw, &end, 10);
    if (end == raw || *end != '\0') {
        return 1'000'000ULL;
    }
    return static_cast<u64>(std::clamp(parsed, 50UL, 1'000'000UL)) * 1000ULL;
}

bool AdrenoProfiler::SchedulerEnabled() const noexcept {
    return qcom_driver.load(std::memory_order_relaxed) &&
           Settings::values.x1_scheduler_sync_log.GetValue();
}

bool AdrenoProfiler::PresentEnabled() const noexcept {
    return qcom_driver.load(std::memory_order_relaxed) &&
           Settings::values.x1_present_frame_log.GetValue();
}

bool AdrenoProfiler::PipelineEnabled() const noexcept {
    return qcom_driver.load(std::memory_order_relaxed) &&
           Settings::values.x1_pipeline_shader_log.GetValue();
}

bool AdrenoProfiler::UploadEnabled() const noexcept {
    return qcom_driver.load(std::memory_order_relaxed) &&
           Settings::values.x1_upload_barrier_log.GetValue();
}

bool AdrenoProfiler::QcomEnabled() const noexcept {
    return qcom_driver.load(std::memory_order_relaxed) &&
           Settings::values.x1_qcom_workaround_log.GetValue();
}

bool AdrenoProfiler::DescriptorEnabled() const noexcept {
    return qcom_driver.load(std::memory_order_relaxed) &&
           Settings::values.x1_descriptor_ring_log.GetValue();
}

bool AdrenoProfiler::Enabled() const noexcept {
    return SchedulerEnabled() || PresentEnabled() || PipelineEnabled() || UploadEnabled() ||
           QcomEnabled();
}

bool AdrenoProfiler::AnyDiagnosticEnabled() const noexcept {
    return Enabled() || DescriptorEnabled();
}

void AdrenoProfiler::Initialize(bool is_qualcomm_proprietary) {
    qcom_driver.store(is_qualcomm_proprietary, std::memory_order_relaxed);
    if (is_qualcomm_proprietary && AnyDiagnosticEnabled()) {
        LOG_INFO(Render_Vulkan,
                 "[X1-FLOW] enabled frame={} sched={} present={} pipe={} upload={} qcom={} dbuf={} "
                 "reportFrames={} slowEventUs={}",
                 CurrentFrame(), SchedulerEnabled(), PresentEnabled(), PipelineEnabled(),
                 UploadEnabled(), QcomEnabled(), DescriptorEnabled(), report_every_frames,
                 slow_event_ns / 1000ULL);
    }
}

void AdrenoProfiler::LogSlow(const char* category, const char* reason, u64 nanoseconds, u64 tick,
                             u64 aux) const {
    if (nanoseconds < slow_event_ns) {
        return;
    }
    LOG_INFO(Render_Vulkan,
             "[X1-FLOW][{}] frame={} thread={} reason={} tick={} aux={} duration={:.3f}ms",
             category, CurrentFrame(), ThreadId(), reason, tick, aux, ToMs(nanoseconds));
}

void AdrenoProfiler::FrameEnd() {
    if (!qcom_driver.load(std::memory_order_relaxed) || !AnyDiagnosticEnabled()) {
        return;
    }

    const u64 frame = frame_id.fetch_add(1, std::memory_order_relaxed) + 1;
    if (!Enabled()) {
        return;
    }

    ++frames_since_report;
    if (frames_since_report < report_every_frames) {
        return;
    }
    const u64 frames = frames_since_report;
    frames_since_report = 0;

    const u64 rp_begin = Take(counters.render_pass_begin);
    const u64 rp_reuse = Take(counters.render_pass_reuse);
    const u64 rp_end = Take(counters.render_pass_end);
    const u64 rp_images = Take(counters.render_pass_images);
    const u64 rp_end_unknown = Take(counters.render_pass_end_unknown);
    const u64 rp_end_deferred = Take(counters.render_pass_end_deferred_clear);
    const u64 rp_end_framebuffer = Take(counters.render_pass_end_framebuffer_change);
    const u64 rp_end_outside = Take(counters.render_pass_end_outside_operation);
    const u64 rp_end_submit = Take(counters.render_pass_end_submit);
    const u64 rp_end_flush_deferred = Take(counters.render_pass_end_flush_deferred_clear);
    const u64 rp_barriers = Take(counters.post_render_pass_image_barriers);
    const u64 deferred_clears = Take(counters.deferred_clears);
    const u64 submits = Take(counters.submits);
    const u64 finish_waits = Take(counters.finish_waits);
    const u64 finish_wait_ns = Take(counters.finish_wait_ns);
    const u64 worker_waits = Take(counters.worker_waits);
    const u64 worker_wait_ns = Take(counters.worker_wait_ns);
    const u64 scheduler_waits = Take(counters.scheduler_waits);
    const u64 scheduler_wait_ns = Take(counters.scheduler_wait_ns);
    const u64 scheduler_gpu_wait_ns = Take(counters.scheduler_gpu_wait_ns);
    const u64 scheduler_pacing_wait_ns = Take(counters.scheduler_pacing_wait_ns);
    const u64 scheduler_forced_flushes = Take(counters.scheduler_forced_flushes);

    const u64 gfx_builds = Take(counters.graphics_pipeline_builds);
    const u64 gfx_failures = Take(counters.graphics_pipeline_failures);
    const u64 gfx_build_ns = Take(counters.graphics_pipeline_build_ns);
    const u64 gfx_waits = Take(counters.graphics_pipeline_waits);
    const u64 gfx_wait_ns = Take(counters.graphics_pipeline_wait_ns);
    const u64 compute_builds = Take(counters.compute_pipeline_builds);
    const u64 compute_failures = Take(counters.compute_pipeline_failures);
    const u64 compute_build_ns = Take(counters.compute_pipeline_build_ns);
    const u64 compute_waits = Take(counters.compute_pipeline_waits);
    const u64 compute_wait_ns = Take(counters.compute_pipeline_wait_ns);
    const u64 shader_emits = Take(counters.shader_emits);
    const u64 shader_emit_ns = Take(counters.shader_emit_ns);
    const u64 shader_bytes = Take(counters.shader_bytes);

    const u64 descriptor_reservations = Take(counters.descriptor_reservations);
    const u64 descriptor_entries = Take(counters.descriptor_entries);
    const u64 descriptor_buffer_entries = Take(counters.descriptor_buffer_entries);
    const u64 descriptor_overflows = Take(counters.descriptor_overflows);
    const u64 descriptor_buffer_binds = Take(counters.descriptor_buffer_binds);

    const u64 staging_upload_requests = Take(counters.staging_upload_requests);
    const u64 staging_upload_bytes = Take(counters.staging_upload_bytes);
    const u64 staging_download_requests = Take(counters.staging_download_requests);
    const u64 staging_download_bytes = Take(counters.staging_download_bytes);
    const u64 deferred_download_requests = Take(counters.staging_deferred_download_requests);
    const u64 deferred_download_bytes = Take(counters.staging_deferred_download_bytes);
    const u64 buffer_copy_calls = Take(counters.buffer_copy_calls);
    const u64 buffer_copy_bytes = Take(counters.buffer_copy_bytes);
    const u64 reordered_upload_calls = Take(counters.reordered_upload_copy_calls);
    const u64 reordered_upload_bytes = Take(counters.reordered_upload_copy_bytes);
    const u64 barriers = Take(counters.barriers);

    const u64 present_waits = Take(counters.present_waits);
    const u64 present_wait_ns = Take(counters.present_wait_ns);
    const u64 acquires = Take(counters.acquires);
    const u64 acquire_ns = Take(counters.acquire_ns);
    const u64 acquire_failures = Take(counters.acquire_failures);
    const u64 presents = Take(counters.presents);
    const u64 present_ns = Take(counters.present_ns);
    const u64 present_failures = Take(counters.present_failures);

    if (SchedulerEnabled()) {
        LOG_INFO(Render_Vulkan,
                 "[X1-FLOW][SCHED] frame={} frames={} wait={} {:.3f}ms gpu={:.3f}ms "
                 "pacing={:.3f}ms forcedFlush={} finish={} {:.3f}ms worker={} {:.3f}ms "
                 "submit={} ({:.2f}/f) RP={}/{}/reuse{} images={} postRPbarrier={} clear={} "
                 "RPend[unknown={} deferred={} framebuffer={} outside={} submit={} flushDeferred={}] "
                 "descReserve={} entries={} dbufEntries={} dbufBinds={} overflow={}",
                 frame, frames, scheduler_waits, ToMs(scheduler_wait_ns),
                 ToMs(scheduler_gpu_wait_ns), ToMs(scheduler_pacing_wait_ns),
                 scheduler_forced_flushes, finish_waits, ToMs(finish_wait_ns), worker_waits,
                 ToMs(worker_wait_ns), submits, PerFrame(submits, frames), rp_begin, rp_end, rp_reuse,
                 rp_images, rp_barriers, deferred_clears, rp_end_unknown, rp_end_deferred,
                 rp_end_framebuffer, rp_end_outside, rp_end_submit, rp_end_flush_deferred,
                 descriptor_reservations, descriptor_entries, descriptor_buffer_entries,
                 descriptor_buffer_binds, descriptor_overflows);
    }

    if (PipelineEnabled()) {
        LOG_INFO(Render_Vulkan,
                 "[X1-FLOW][PIPE] frame={} frames={} gfx={} fail={} {:.3f}ms gfxWait={} {:.3f}ms "
                 "compute={} fail={} {:.3f}ms computeWait={} {:.3f}ms shaderEmit={} {:.3f}ms "
                 "bytes={}",
                 frame, frames, gfx_builds, gfx_failures, ToMs(gfx_build_ns), gfx_waits,
                 ToMs(gfx_wait_ns), compute_builds, compute_failures, ToMs(compute_build_ns),
                 compute_waits, ToMs(compute_wait_ns), shader_emits, ToMs(shader_emit_ns),
                 shader_bytes);
    }

    if (PresentEnabled()) {
        LOG_INFO(Render_Vulkan,
                 "[X1-FLOW][PRESENT] frame={} frames={} waits={} {:.3f}ms acquire={} fail={} "
                 "{:.3f}ms present={} fail={} {:.3f}ms",
                 frame, frames, present_waits, ToMs(present_wait_ns), acquires, acquire_failures,
                 ToMs(acquire_ns), presents, present_failures, ToMs(present_ns));
    }

    if (UploadEnabled()) {
        LOG_INFO(Render_Vulkan,
                 "[X1-FLOW][UPLOAD] frame={} frames={} stagingUpload={} {:.3f}MiB "
                 "stagingDownload={} {:.3f}MiB deferredDownload={} {:.3f}MiB bufferCopy={} "
                 "{:.3f}MiB reorderedUpload={} {:.3f}MiB barriers={}",
                 frame, frames, staging_upload_requests, ToMiB(staging_upload_bytes),
                 staging_download_requests, ToMiB(staging_download_bytes), deferred_download_requests,
                 ToMiB(deferred_download_bytes), buffer_copy_calls, ToMiB(buffer_copy_bytes),
                 reordered_upload_calls, ToMiB(reordered_upload_bytes), barriers);
    }

    if (QcomEnabled()) {
        LOG_INFO(Render_Vulkan,
                 "[X1-FLOW][QCOM] frame={} frames={} descriptorTiler={} dynamicStorage={} "
                 "shaderProfile={} customBorder={} borderSwizzle={}",
                 frame, frames,
                 Take(counters.qcom[static_cast<size_t>(QcomEvent::DescriptorTilerPolicy)]),
                 Take(counters.qcom[static_cast<size_t>(QcomEvent::DynamicStorageLimit)]),
                 Take(counters.qcom[static_cast<size_t>(QcomEvent::ShaderProfile)]),
                 Take(counters.qcom[static_cast<size_t>(QcomEvent::CustomBorderColor)]),
                 Take(counters.qcom[static_cast<size_t>(QcomEvent::BorderColorSwizzle)]));
    } else {
        for (auto& value : counters.qcom) {
            Take(value);
        }
    }
}

void AdrenoProfiler::RecordRenderPassBegin(u32 image_count) {
    if (!SchedulerEnabled()) {
        return;
    }
    counters.render_pass_begin.fetch_add(1, std::memory_order_relaxed);
    counters.render_pass_images.fetch_add(image_count, std::memory_order_relaxed);
}

void AdrenoProfiler::RecordRenderPassReuse() {
    if (SchedulerEnabled()) {
        counters.render_pass_reuse.fetch_add(1, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordRenderPassEnd(u32, RenderPassEndReason reason) {
    if (!SchedulerEnabled()) {
        return;
    }
    counters.render_pass_end.fetch_add(1, std::memory_order_relaxed);
    switch (reason) {
    case RenderPassEndReason::Unknown:
        counters.render_pass_end_unknown.fetch_add(1, std::memory_order_relaxed);
        break;
    case RenderPassEndReason::DeferredClear:
        counters.render_pass_end_deferred_clear.fetch_add(1, std::memory_order_relaxed);
        break;
    case RenderPassEndReason::FramebufferChange:
        counters.render_pass_end_framebuffer_change.fetch_add(1, std::memory_order_relaxed);
        break;
    case RenderPassEndReason::OutsideOperation:
        counters.render_pass_end_outside_operation.fetch_add(1, std::memory_order_relaxed);
        break;
    case RenderPassEndReason::Submit:
        counters.render_pass_end_submit.fetch_add(1, std::memory_order_relaxed);
        break;
    case RenderPassEndReason::FlushDeferredClear:
        counters.render_pass_end_flush_deferred_clear.fetch_add(1, std::memory_order_relaxed);
        break;
    }
}

void AdrenoProfiler::RecordPostRenderPassImageBarriers(u32 image_count) {
    if (SchedulerEnabled()) {
        counters.post_render_pass_image_barriers.fetch_add(image_count, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordDeferredClear() {
    if (SchedulerEnabled()) {
        counters.deferred_clears.fetch_add(1, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordSubmit() {
    if (SchedulerEnabled()) {
        counters.submits.fetch_add(1, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordFinishWait(u64 nanoseconds) {
    if (!SchedulerEnabled()) {
        return;
    }
    counters.finish_waits.fetch_add(1, std::memory_order_relaxed);
    counters.finish_wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    LogSlow("SCHED", "finish-wait", nanoseconds);
}

void AdrenoProfiler::RecordWorkerWait(u64 nanoseconds) {
    if (!SchedulerEnabled()) {
        return;
    }
    counters.worker_waits.fetch_add(1, std::memory_order_relaxed);
    counters.worker_wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    LogSlow("SCHED", "worker-wait", nanoseconds);
}

void AdrenoProfiler::RecordGraphicsPipelineBuild(u64 nanoseconds, bool success) {
    if (!PipelineEnabled()) {
        return;
    }
    counters.graphics_pipeline_builds.fetch_add(1, std::memory_order_relaxed);
    counters.graphics_pipeline_build_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    if (!success) {
        counters.graphics_pipeline_failures.fetch_add(1, std::memory_order_relaxed);
    }
    LogSlow("PIPE", success ? "graphics-build" : "graphics-build-fail", nanoseconds);
}

void AdrenoProfiler::RecordComputePipelineBuild(u64 nanoseconds, bool success) {
    if (!PipelineEnabled()) {
        return;
    }
    counters.compute_pipeline_builds.fetch_add(1, std::memory_order_relaxed);
    counters.compute_pipeline_build_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    if (!success) {
        counters.compute_pipeline_failures.fetch_add(1, std::memory_order_relaxed);
    }
    LogSlow("PIPE", success ? "compute-build" : "compute-build-fail", nanoseconds);
}

void AdrenoProfiler::RecordDescriptorReservation(size_t entries, bool descriptor_buffer) {
    if (!SchedulerEnabled()) {
        return;
    }
    counters.descriptor_reservations.fetch_add(1, std::memory_order_relaxed);
    counters.descriptor_entries.fetch_add(static_cast<u64>(entries), std::memory_order_relaxed);
    if (descriptor_buffer) {
        counters.descriptor_buffer_entries.fetch_add(static_cast<u64>(entries),
                                                     std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordDescriptorOverflow() {
    if (SchedulerEnabled()) {
        counters.descriptor_overflows.fetch_add(1, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordDescriptorBufferBind() {
    if (SchedulerEnabled()) {
        counters.descriptor_buffer_binds.fetch_add(1, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordStagingRequest(u64 bytes, bool download, bool deferred) {
    if (!UploadEnabled()) {
        return;
    }
    if (download) {
        counters.staging_download_requests.fetch_add(1, std::memory_order_relaxed);
        counters.staging_download_bytes.fetch_add(bytes, std::memory_order_relaxed);
        if (deferred) {
            counters.staging_deferred_download_requests.fetch_add(1, std::memory_order_relaxed);
            counters.staging_deferred_download_bytes.fetch_add(bytes, std::memory_order_relaxed);
        }
    } else {
        counters.staging_upload_requests.fetch_add(1, std::memory_order_relaxed);
        counters.staging_upload_bytes.fetch_add(bytes, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordBufferCopy(u64 bytes, bool reordered_upload) {
    if (!UploadEnabled()) {
        return;
    }
    counters.buffer_copy_calls.fetch_add(1, std::memory_order_relaxed);
    counters.buffer_copy_bytes.fetch_add(bytes, std::memory_order_relaxed);
    if (reordered_upload) {
        counters.reordered_upload_copy_calls.fetch_add(1, std::memory_order_relaxed);
        counters.reordered_upload_copy_bytes.fetch_add(bytes, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordSchedulerWait(u64 tick, bool forced_flush, u64 gpu_wait_ns,
                                         u64 pacing_wait_ns) {
    if (!SchedulerEnabled()) {
        return;
    }
    const u64 total = gpu_wait_ns + pacing_wait_ns;
    counters.scheduler_waits.fetch_add(1, std::memory_order_relaxed);
    counters.scheduler_wait_ns.fetch_add(total, std::memory_order_relaxed);
    counters.scheduler_gpu_wait_ns.fetch_add(gpu_wait_ns, std::memory_order_relaxed);
    counters.scheduler_pacing_wait_ns.fetch_add(pacing_wait_ns, std::memory_order_relaxed);
    if (forced_flush) {
        counters.scheduler_forced_flushes.fetch_add(1, std::memory_order_relaxed);
    }
    LogSlow("SCHED", forced_flush ? "wait-forced-flush" : "wait", total, tick,
            pacing_wait_ns);
}

void AdrenoProfiler::RecordPresentWait(const char* reason, u64 nanoseconds) {
    if (!PresentEnabled()) {
        return;
    }
    counters.present_waits.fetch_add(1, std::memory_order_relaxed);
    counters.present_wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    LogSlow("PRESENT", reason, nanoseconds);
}

void AdrenoProfiler::RecordAcquire(u64 nanoseconds, int result) {
    if (!PresentEnabled()) {
        return;
    }
    counters.acquires.fetch_add(1, std::memory_order_relaxed);
    counters.acquire_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    if (result != 0) {
        counters.acquire_failures.fetch_add(1, std::memory_order_relaxed);
    }
    LogSlow("PRESENT", result == 0 ? "acquire" : "acquire-nonzero", nanoseconds, 0,
            static_cast<u64>(static_cast<u32>(result)));
}

void AdrenoProfiler::RecordPresentCall(u64 nanoseconds, int result) {
    if (!PresentEnabled()) {
        return;
    }
    counters.presents.fetch_add(1, std::memory_order_relaxed);
    counters.present_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    if (result != 0) {
        counters.present_failures.fetch_add(1, std::memory_order_relaxed);
    }
    LogSlow("PRESENT", result == 0 ? "present" : "present-nonzero", nanoseconds, 0,
            static_cast<u64>(static_cast<u32>(result)));
}

void AdrenoProfiler::RecordShaderEmit(const char* kind, u64 nanoseconds, u64 bytes) {
    if (!PipelineEnabled()) {
        return;
    }
    counters.shader_emits.fetch_add(1, std::memory_order_relaxed);
    counters.shader_emit_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
    counters.shader_bytes.fetch_add(bytes, std::memory_order_relaxed);
    LogSlow("PIPE", kind, nanoseconds, 0, bytes);
}

void AdrenoProfiler::RecordPipelineWait(bool compute, u64 nanoseconds) {
    if (!PipelineEnabled()) {
        return;
    }
    if (compute) {
        counters.compute_pipeline_waits.fetch_add(1, std::memory_order_relaxed);
        counters.compute_pipeline_wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
        LogSlow("PIPE", "compute-ready-wait", nanoseconds);
    } else {
        counters.graphics_pipeline_waits.fetch_add(1, std::memory_order_relaxed);
        counters.graphics_pipeline_wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
        LogSlow("PIPE", "graphics-ready-wait", nanoseconds);
    }
}

void AdrenoProfiler::RecordBarrier(const char*, u64 count) {
    if (UploadEnabled()) {
        counters.barriers.fetch_add(count, std::memory_order_relaxed);
    }
}

void AdrenoProfiler::RecordQcomHit(QcomEvent event) {
    // Constructor-time policy hooks can run before RendererVulkan::Initialize().
    if (!Settings::values.x1_qcom_workaround_log.GetValue() || event == QcomEvent::Count) {
        return;
    }
    counters.qcom[static_cast<size_t>(event)].fetch_add(1, std::memory_order_relaxed);
}

void AdrenoProfiler::RecordDescriptorStall(const char* reason, u64 tick, u64 nanoseconds) {
    if (!DescriptorEnabled()) {
        return;
    }
    LogSlow("DBUF", reason, nanoseconds, tick);
}

} // namespace Vulkan
