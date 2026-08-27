#!/usr/bin/env python3
"""Add observation-only GPU-thread / command-processing attribution after frame-build attribution."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_gpu_command_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/video_core/x1_gpu_command_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_gpu_command_profiler.h must be copied before this pass")

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_frame_build_attribution_log{
        linkage, false, "x1_frame_build_attribution_log", Category::Debugging};
'''
    text = replace_once(text, anchor, anchor + '''    Setting<bool> x1_gpu_command_attribution_log{
        linkage, false, "x1_gpu_command_attribution_log", Category::Debugging};
''', "gpu-command setting")
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_dequeue_attribution_log_checkbox{};
    QCheckBox* x1_frame_build_attribution_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(text, anchor, '''    QCheckBox* x1_dequeue_attribution_log_checkbox{};
    QCheckBox* x1_frame_build_attribution_log_checkbox{};
    QCheckBox* x1_gpu_command_attribution_log_checkbox{};

    const Core::System& system;
''', "gpu-command widget member")
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
    anchor = '''    x1_frame_build_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Frame Build Attribution"), this);

'''
    text = replace_once(text, anchor, anchor + '''    x1_gpu_command_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: GPU Command Attribution"), this);

''', "gpu-command widget construction")

    anchor = '''    x1_frame_build_attribution_log_checkbox->setToolTip(
        tr("Measure CPU-side Vulkan frame-build wall time: Draw preparation, GraphicsPipeline "
           "Configure sub-stages, Dispatch, Clear and DrawTexture. Disabled by default."));

'''
    text = replace_once(text, anchor, anchor + '''    x1_gpu_command_attribution_log_checkbox->setToolTip(
        tr("Measure asynchronous GPU worker queue wait/active time plus Scheduler and DmaPusher "
           "command-processing wall time. Observation-only and disabled by default."));

''', "gpu-command tooltip")

    anchor = '''    ui->gridLayout_1->addWidget(x1_frame_build_attribution_log_checkbox, 9, 0, 1, 2);

'''
    text = replace_once(text, anchor, anchor + '''    ui->gridLayout_1->addWidget(x1_gpu_command_attribution_log_checkbox, 9, 2, 1, 2);

''', "gpu-command layout")

    anchor = '''    x1_frame_build_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_frame_build_attribution_log_checkbox->setChecked(
        Settings::values.x1_frame_build_attribution_log.GetValue());
'''
    text = replace_once(text, anchor, anchor + '''    x1_gpu_command_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_gpu_command_attribution_log_checkbox->setChecked(
        Settings::values.x1_gpu_command_attribution_log.GetValue());
''', "gpu-command widget state")

    anchor = '''    Settings::values.x1_frame_build_attribution_log =
        x1_frame_build_attribution_log_checkbox->isChecked();
'''
    text = replace_once(text, anchor, anchor + '''    Settings::values.x1_gpu_command_attribution_log =
        x1_gpu_command_attribution_log_checkbox->isChecked();
''', "gpu-command widget apply")

    anchor = '''    x1_frame_build_attribution_log_checkbox->setText(
        tr("X1 Log: Frame Build Attribution"));
}
'''
    text = replace_once(text, anchor, '''    x1_frame_build_attribution_log_checkbox->setText(
        tr("X1 Log: Frame Build Attribution"));
    x1_gpu_command_attribution_log_checkbox->setText(
        tr("X1 Log: GPU Command Attribution"));
}
''', "gpu-command widget retranslate")
    ui_cpp.write_text(text, encoding="utf-8")

    gpu_thread = root / "src/video_core/gpu_thread.cpp"
    text = gpu_thread.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/host1x/host1x.h"\n',
        '#include "video_core/host1x/host1x.h"\n#include "video_core/x1_gpu_command_profiler.h"\n',
        "gpu-thread profiler include")

    anchor = '''        CommandDataContainer next;
        while (!stop_token.stop_requested()) {
            state.queue.PopWait(next, stop_token);
            if (stop_token.stop_requested()) {
                break;
            }
            if (auto* submit_list = std::get_if<SubmitListCommand>(&next.data)) {
                scheduler.Push(system.GPU(), submit_list->channel, std::move(submit_list->entries));
            } else if (std::holds_alternative<GPUTickCommand>(next.data)) {
                system.GPU().TickWork();
            } else if (const auto* flush = std::get_if<FlushRegionCommand>(&next.data)) {
                renderer.ReadRasterizer()->FlushRegion(flush->addr, flush->size);
            } else if (const auto* invalidate = std::get_if<InvalidateRegionCommand>(&next.data)) {
                renderer.ReadRasterizer()->OnCacheInvalidation(invalidate->addr, invalidate->size);
            } else {
                ASSERT(false);
            }
'''
    replacement = '''        CommandDataContainer next;
        while (!stop_token.stop_requested()) {
            auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
            const bool x1_gpu_command_log = x1_gpu_command_profiler.Enabled();
            const auto x1_queue_wait_start =
                x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                                   : VideoCore::X1GpuCommandProfiler::TimePoint{};
            state.queue.PopWait(next, stop_token);
            if (x1_gpu_command_log) {
                x1_gpu_command_profiler.RecordWorkerQueueWait(
                    VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_queue_wait_start));
            }
            if (stop_token.stop_requested()) {
                break;
            }

            const auto x1_worker_start =
                x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                                   : VideoCore::X1GpuCommandProfiler::TimePoint{};
            u32 x1_worker_kind = 4;
            if (auto* submit_list = std::get_if<SubmitListCommand>(&next.data)) {
                x1_worker_kind = 0;
                scheduler.Push(system.GPU(), submit_list->channel, std::move(submit_list->entries));
            } else if (std::holds_alternative<GPUTickCommand>(next.data)) {
                x1_worker_kind = 1;
                system.GPU().TickWork();
            } else if (const auto* flush = std::get_if<FlushRegionCommand>(&next.data)) {
                x1_worker_kind = 2;
                renderer.ReadRasterizer()->FlushRegion(flush->addr, flush->size);
            } else if (const auto* invalidate = std::get_if<InvalidateRegionCommand>(&next.data)) {
                x1_worker_kind = 3;
                renderer.ReadRasterizer()->OnCacheInvalidation(invalidate->addr, invalidate->size);
            } else {
                ASSERT(false);
            }
            if (x1_gpu_command_log) {
                x1_gpu_command_profiler.RecordWorkerCommand(
                    VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_worker_start), x1_worker_kind);
            }
'''
    text = replace_once(text, anchor, replacement, "GPU worker queue/active attribution")

    anchor = '''u64 ThreadManager::PushCommand(CommandData&& command_data, bool block, bool is_async) {
    if (!is_async) {
        // In synchronous GPU mode, block the caller until the command has executed
        block = true;
    }

    std::unique_lock lk(state.write_lock);
    const u64 fence{++state.last_fence};
    state.queue.EmplaceWait(std::move(command_data), fence, block);

    if (block) {
        state.cv.wait(lk, thread.get_stop_token(), [this, fence] {
            return fence <= state.signaled_fence.load(std::memory_order_relaxed);
        });
    }

    return fence;
}
'''
    replacement = '''u64 ThreadManager::PushCommand(CommandData&& command_data, bool block, bool is_async) {
    auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
    const bool x1_gpu_command_log = x1_gpu_command_profiler.Enabled();
    const auto x1_push_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};
    u64 x1_block_wait_ns{};

    if (!is_async) {
        // In synchronous GPU mode, block the caller until the command has executed
        block = true;
    }

    std::unique_lock lk(state.write_lock);
    const u64 fence{++state.last_fence};
    state.queue.EmplaceWait(std::move(command_data), fence, block);

    if (block) {
        const auto x1_block_start =
            x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                               : VideoCore::X1GpuCommandProfiler::TimePoint{};
        state.cv.wait(lk, thread.get_stop_token(), [this, fence] {
            return fence <= state.signaled_fence.load(std::memory_order_relaxed);
        });
        if (x1_gpu_command_log) {
            x1_block_wait_ns = VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_block_start);
        }
    }

    if (x1_gpu_command_log) {
        x1_gpu_command_profiler.RecordPushCommand(
            VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_push_start), x1_block_wait_ns, block);
    }
    return fence;
}
'''
    text = replace_once(text, anchor, replacement, "PushCommand attribution")
    gpu_thread.write_text(text, encoding="utf-8")

    scheduler = root / "src/video_core/control/scheduler.cpp"
    text = scheduler.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/gpu.h"\n',
        '#include "video_core/gpu.h"\n#include "video_core/x1_gpu_command_profiler.h"\n',
        "control scheduler profiler include")
    anchor = '''void Scheduler::Push(GPU& gpu, s32 channel, CommandList&& entries) {
    std::shared_ptr<ChannelState> channel_state;
    {
        std::unique_lock lk(scheduling_guard);
        auto it = channels.find(channel);
        ASSERT(it != channels.end());
        channel_state = it->second;
        gpu.BindChannel(channel_state->bind_id);
    }
    // Process commands outside the lock to reduce contention.
    // Multiple channels can prepare their commands in parallel.
    channel_state->payload->dma_pusher.Push(std::move(entries));
    channel_state->payload->dma_pusher.DispatchCalls();
}
'''
    replacement = '''void Scheduler::Push(GPU& gpu, s32 channel, CommandList&& entries) {
    auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
    const bool x1_gpu_command_log = x1_gpu_command_profiler.Enabled();
    const auto x1_sched_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};
    const auto x1_bind_start = x1_sched_start;

    std::shared_ptr<ChannelState> channel_state;
    {
        std::unique_lock lk(scheduling_guard);
        auto it = channels.find(channel);
        ASSERT(it != channels.end());
        channel_state = it->second;
        gpu.BindChannel(channel_state->bind_id);
    }
    const u64 x1_bind_ns =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_bind_start) : 0;

    // Process commands outside the lock to reduce contention.
    // Multiple channels can prepare their commands in parallel.
    channel_state->payload->dma_pusher.Push(std::move(entries));
    const auto x1_dispatch_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};
    channel_state->payload->dma_pusher.DispatchCalls();
    const u64 x1_dispatch_ns =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_dispatch_start) : 0;

    if (x1_gpu_command_log) {
        x1_gpu_command_profiler.RecordSchedulerPush(
            VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_sched_start), x1_bind_ns,
            x1_dispatch_ns);
    }
}
'''
    text = replace_once(text, anchor, replacement, "Scheduler::Push attribution")
    scheduler.write_text(text, encoding="utf-8")

    dma = root / "src/video_core/dma_pusher.cpp"
    text = dma.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/rasterizer_interface.h"\n',
        '#include "video_core/rasterizer_interface.h"\n#include "video_core/x1_gpu_command_profiler.h"\n',
        "dma profiler include")

    anchor = '''void DmaPusher::DispatchCalls() {
    dma_pushbuffer_subindex = 0;
    dma_state.is_last_call = true;
    while (system.IsPoweredOn()) {
        if (!Step()) {
            break;
        }
    }
    system.GPU().FlushCommands();
    system.GPU().OnCommandListEnd();
}
'''
    replacement = '''void DmaPusher::DispatchCalls() {
    auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
    const bool x1_gpu_command_log = x1_gpu_command_profiler.Enabled();
    const auto x1_dma_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};
    u64 x1_step_calls{};

    dma_pushbuffer_subindex = 0;
    dma_state.is_last_call = true;
    const auto x1_loop_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};
    while (system.IsPoweredOn()) {
        if (!Step()) {
            break;
        }
        if (x1_gpu_command_log) {
            ++x1_step_calls;
        }
    }
    const u64 x1_loop_ns =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_loop_start) : 0;

    const auto x1_tail_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};
    system.GPU().FlushCommands();
    system.GPU().OnCommandListEnd();
    const u64 x1_tail_ns =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_tail_start) : 0;

    if (x1_gpu_command_log) {
        x1_gpu_command_profiler.RecordDmaDispatch(
            VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_dma_start), x1_loop_ns, x1_tail_ns,
            x1_step_calls);
    }
}
'''
    text = replace_once(text, anchor, replacement, "DmaPusher::DispatchCalls attribution")

    anchor = '''    if (signal_sync && !synced) {
        std::unique_lock lk(sync_mutex);
        sync_cv.wait(lk, [this]() { return synced; });
        signal_sync = false;
        synced = false;
    }
'''
    replacement = '''    if (signal_sync && !synced) {
        auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
        const bool x1_gpu_command_log = x1_gpu_command_profiler.Enabled();
        const auto x1_sync_wait_start =
            x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                               : VideoCore::X1GpuCommandProfiler::TimePoint{};
        std::unique_lock lk(sync_mutex);
        sync_cv.wait(lk, [this]() { return synced; });
        if (x1_gpu_command_log) {
            x1_gpu_command_profiler.RecordDmaSyncWait(
                VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_sync_wait_start));
        }
        signal_sync = false;
        synced = false;
    }
'''
    text = replace_once(text, anchor, replacement, "DmaPusher sync wait attribution")

    anchor = '''void DmaPusher::ProcessCommands(std::span<const CommandHeader> commands) {
    for (size_t index = 0; index < commands.size();) {
'''
    replacement = '''void DmaPusher::ProcessCommands(std::span<const CommandHeader> commands) {
    auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
    const bool x1_gpu_command_log = x1_gpu_command_profiler.Enabled();
    const auto x1_process_start =
        x1_gpu_command_log ? VideoCore::X1GpuCommandProfiler::Now()
                           : VideoCore::X1GpuCommandProfiler::TimePoint{};

    for (size_t index = 0; index < commands.size();) {
'''
    text = replace_once(text, anchor, replacement, "ProcessCommands timing start")

    anchor = '''            index++;
        }
    }
}

void DmaPusher::SetState(const CommandHeader& command_header) {
'''
    replacement = '''            index++;
        }
    }

    if (x1_gpu_command_log) {
        x1_gpu_command_profiler.RecordProcessCommands(
            VideoCore::X1GpuCommandProfiler::ElapsedNs(x1_process_start), commands.size());
    }
}

void DmaPusher::SetState(const CommandHeader& command_header) {
'''
    text = replace_once(text, anchor, replacement, "ProcessCommands timing end")

    anchor = '''void DmaPusher::CallMethod(u32 argument) {
    if (dma_state.method < non_puller_methods) {
'''
    replacement = '''void DmaPusher::CallMethod(u32 argument) {
    auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
    if (x1_gpu_command_profiler.Enabled()) {
        x1_gpu_command_profiler.CountCallMethod();
    }
    if (dma_state.method < non_puller_methods) {
'''
    text = replace_once(text, anchor, replacement, "CallMethod count")

    anchor = '''void DmaPusher::CallMultiMethod(const u32* base_start, u32 num_methods) {
    if (dma_state.method < non_puller_methods) {
'''
    replacement = '''void DmaPusher::CallMultiMethod(const u32* base_start, u32 num_methods) {
    auto& x1_gpu_command_profiler = VideoCore::X1GpuCommandProfiler::Get();
    if (x1_gpu_command_profiler.Enabled()) {
        x1_gpu_command_profiler.CountCallMultiMethod(num_methods);
    }
    if (dma_state.method < non_puller_methods) {
'''
    text = replace_once(text, anchor, replacement, "CallMultiMethod count")
    dma.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/renderer_vulkan/vk_x1_frame_build_profiler.h"\n',
        '#include "video_core/renderer_vulkan/vk_x1_frame_build_profiler.h"\n#include "video_core/x1_gpu_command_profiler.h"\n',
        "rasterizer gpu-command profiler include")
    anchor = '''    X1FrameBuildProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    replacement = '''    X1FrameBuildProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    VideoCore::X1GpuCommandProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(text, anchor, replacement, "gpu-command profiler initialization")

    anchor = '''    x1_build_profiler.FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    replacement = '''    x1_build_profiler.FrameEnd();
    VideoCore::X1GpuCommandProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(text, anchor, replacement, "gpu-command frame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        settings: ["x1_gpu_command_attribution_log"],
        ui_cpp: ["X1 Log: GPU Command Attribution"],
        gpu_thread: ["RecordWorkerQueueWait", "RecordPushCommand"],
        scheduler: ["RecordSchedulerPush"],
        dma: ["RecordDmaDispatch", "RecordProcessCommands", "CountCallMethod", "CountCallMultiMethod"],
        rasterizer: ["X1GpuCommandProfiler::Get().Initialize", "X1GpuCommandProfiler::Get().FrameEnd"],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    print("Transplanted exact dc95 X1 GPU-command attribution over frame-build harness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
