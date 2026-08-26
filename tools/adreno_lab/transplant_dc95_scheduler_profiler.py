#!/usr/bin/env python3
from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_scheduler_profiler.py <vk_scheduler.cpp>")

    path = Path(sys.argv[1])
    header = path.with_suffix(".h")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_command_pool.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_command_pool.h"\n',
        "include",
    )

    text = replace_once(
        text,
        '''    const u64 presubmit_tick = CurrentTick();
    SubmitExecution(signal_semaphore, wait_semaphore);
    Wait(presubmit_tick);
    AllocateNewContext();''',
        '''    const u64 presubmit_tick = CurrentTick();
    SubmitExecution(signal_semaphore, wait_semaphore);
    auto& profiler = AdrenoProfiler::Get();
    const auto wait_start =
        profiler.SchedulerEnabled() ? AdrenoProfiler::Now() : AdrenoProfiler::TimePoint{};
    Wait(presubmit_tick);
    if (profiler.SchedulerEnabled()) {
        profiler.RecordFinishWait(AdrenoProfiler::ElapsedNs(wait_start));
    }
    AllocateNewContext();''',
        "Finish",
    )

    text = replace_once(
        text,
        '''void Scheduler::WaitWorker() {
    DispatchWork();

    // Ensure the queue is drained.
    {
        std::unique_lock ql{queue_mutex};
        event_cv.wait(ql, [this] { return work_queue.empty(); });
    }

    // Now wait for execution to finish.
    std::scoped_lock el{execution_mutex};
}''',
        '''void Scheduler::WaitWorker() {
    auto& profiler = AdrenoProfiler::Get();
    const auto wait_start =
        profiler.SchedulerEnabled() ? AdrenoProfiler::Now() : AdrenoProfiler::TimePoint{};
    DispatchWork();

    // Ensure the queue is drained.
    {
        std::unique_lock ql{queue_mutex};
        event_cv.wait(ql, [this] { return work_queue.empty(); });
    }

    // Now wait for execution to finish.
    std::scoped_lock el{execution_mutex};
    if (profiler.SchedulerEnabled()) {
        profiler.RecordWorkerWait(AdrenoProfiler::ElapsedNs(wait_start));
    }
}''',
        "WaitWorker",
    )

    text = replace_once(
        text,
        '''    num_renderpass_images = framebuffer->NumImages();
    renderpass_images = framebuffer->Images();
    renderpass_image_ranges = framebuffer->ImageRanges();
}''',
        '''    num_renderpass_images = framebuffer->NumImages();
    renderpass_images = framebuffer->Images();
    renderpass_image_ranges = framebuffer->ImageRanges();
    AdrenoProfiler::Get().RecordRenderPassBegin(framebuffer->NumImages());
}''',
        "BeginRenderPassImpl",
    )

    text = replace_once(
        text,
        '''    const DeferredClear dc = deferred_clear;
    deferred_clear = {};

    std::array<VkClearValue, 9> clear_values{};''',
        '''    const DeferredClear dc = deferred_clear;
    deferred_clear = {};
    AdrenoProfiler::Get().RecordDeferredClear();

    std::array<VkClearValue, 9> clear_values{};''',
        "RealizeDeferredClear",
    )

    # Preserve exact dc95 behavior while tagging the reason for each pre-existing pass end.
    text = replace_once(
        text,
        '''    const VkRenderPass renderpass = dc.framebuffer->RenderPassVariant(
        dc.color_clear_mask, dc.depth_stencil, color_discard_mask);
    EndRenderPass();
    BeginRenderPassImpl(dc.framebuffer, renderpass, clear_values.data(), count);''',
        '''    const VkRenderPass renderpass = dc.framebuffer->RenderPassVariant(
        dc.color_clear_mask, dc.depth_stencil, color_discard_mask);
    EndRenderPass(RenderPassEndReason::DeferredClear);
    BeginRenderPassImpl(dc.framebuffer, renderpass, clear_values.data(), count);''',
        "deferred clear end reason",
    )

    text = replace_once(
        text,
        '''    if (deferred_clear.framebuffer != nullptr && deferred_clear.framebuffer != framebuffer) {
        RealizeDeferredClear();
        EndRenderPass();
    }
    deferred_clear.framebuffer = framebuffer;
    deferred_clear.color_clear_mask''',
        '''    if (deferred_clear.framebuffer != nullptr && deferred_clear.framebuffer != framebuffer) {
        RealizeDeferredClear();
        EndRenderPass(RenderPassEndReason::DeferredClear);
    }
    deferred_clear.framebuffer = framebuffer;
    deferred_clear.color_clear_mask''',
        "color deferred end reason",
    )

    text = replace_once(
        text,
        '''    if (deferred_clear.framebuffer != nullptr && deferred_clear.framebuffer != framebuffer) {
        RealizeDeferredClear();
        EndRenderPass();
    }
    deferred_clear.framebuffer = framebuffer;
    deferred_clear.depth_stencil''',
        '''    if (deferred_clear.framebuffer != nullptr && deferred_clear.framebuffer != framebuffer) {
        RealizeDeferredClear();
        EndRenderPass(RenderPassEndReason::DeferredClear);
    }
    deferred_clear.framebuffer = framebuffer;
    deferred_clear.depth_stencil''',
        "depth deferred end reason",
    )

    text = replace_once(
        text,
        '''    if (renderpass == state.renderpass && framebuffer_handle == state.framebuffer &&
        render_area.width == state.render_area.width &&
        render_area.height == state.render_area.height) {
        return;
    }
    // Ends any active pass and realizes a deferred clear
    EndRenderPass();''',
        '''    if (renderpass == state.renderpass && framebuffer_handle == state.framebuffer &&
        render_area.width == state.render_area.width &&
        render_area.height == state.render_area.height) {
        AdrenoProfiler::Get().RecordRenderPassReuse();
        return;
    }
    // Ends any active pass and realizes a deferred clear
    EndRenderPass(RenderPassEndReason::FramebufferChange);''',
        "RequestRenderpass reuse/reason",
    )

    text = replace_once(
        text,
        '''void Scheduler::RequestOutsideRenderPassOperationContext() {
    EndRenderPass();
}''',
        '''void Scheduler::RequestOutsideRenderPassOperationContext() {
    EndRenderPass(RenderPassEndReason::OutsideOperation);
}''',
        "outside operation reason",
    )

    text = replace_once(
        text,
        '''    state.descriptor_buffer_bound = true;
    state.descriptor_buffer_chunk = descriptor_chunk;
    return true;''',
        '''    state.descriptor_buffer_bound = true;
    state.descriptor_buffer_chunk = descriptor_chunk;
    AdrenoProfiler::Get().RecordDescriptorBufferBind();
    return true;''',
        "UpdateDescriptorBufferChunk",
    )

    barrier = (
        "        upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, "
        "VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);\n"
    )
    text = replace_once(
        text,
        barrier,
        barrier + '        AdrenoProfiler::Get().RecordBarrier("submit-upload", 1);\n',
        "submit upload barrier",
    )

    text = replace_once(
        text,
        '''    chunk->MarkSubmit();
    DispatchWork();
    return signal_value;''',
        '''    chunk->MarkSubmit();
    AdrenoProfiler::Get().RecordSubmit();
    DispatchWork();
    return signal_value;''',
        "SubmitExecution",
    )

    text = replace_once(
        text,
        '''void Scheduler::EndPendingOperations() {
    query_cache->CounterReset(VideoCommon::QueryType::ZPassPixelCount64);
    EndRenderPass();
}

void Scheduler::EndRenderPass()
    {''',
        '''void Scheduler::EndPendingOperations() {
    query_cache->CounterReset(VideoCommon::QueryType::ZPassPixelCount64);
    EndRenderPass(RenderPassEndReason::Submit);
}

void Scheduler::EndRenderPass(RenderPassEndReason reason)
    {''',
        "EndPendingOperations/EndRenderPass reason",
    )

    text = replace_once(
        text,
        '''        if (!state.renderpass) {
            return;
        }

        query_cache->CounterClose(VideoCommon::QueryType::StreamingByteCount);''',
        '''        if (!state.renderpass) {
            return;
        }

        AdrenoProfiler::Get().RecordRenderPassEnd(num_renderpass_images, reason);
        AdrenoProfiler::Get().RecordPostRenderPassImageBarriers(num_renderpass_images);

        query_cache->CounterClose(VideoCommon::QueryType::StreamingByteCount);''',
        "EndRenderPass metrics",
    )

    path.write_text(text, encoding="utf-8")

    htext = header.read_text(encoding="utf-8")
    htext = replace_once(
        htext,
        'class StateTracker;\n\nstruct QueryCacheParams;\n',
        'class StateTracker;\nenum class RenderPassEndReason : u8;\n\nstruct QueryCacheParams;\n',
        "scheduler reason forward declaration",
    )
    htext = replace_once(
        htext,
        '    void EndRenderPass();\n',
        '    void EndRenderPass(RenderPassEndReason reason);\n',
        "scheduler EndRenderPass declaration",
    )
    header.write_text(htext, encoding="utf-8")

    print(f"Transplanted exact dc95 scheduler full-flow profiler hooks into {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
