#!/usr/bin/env python3
"""Add observation-only NVDRV/GPFIFO submission-gap attribution after GPU-command attribution."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_gpu_submit_gap_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/video_core/x1_gpu_submit_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_gpu_submit_profiler.h must be copied before this pass")

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_gpu_command_attribution_log{
        linkage, false, "x1_gpu_command_attribution_log", Category::Debugging};
'''
    text = replace_once(text, anchor, anchor + '''    Setting<bool> x1_gpu_submit_gap_attribution_log{
        linkage, false, "x1_gpu_submit_gap_attribution_log", Category::Debugging};
''', "GPU-submit setting")
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_frame_build_attribution_log_checkbox{};
    QCheckBox* x1_gpu_command_attribution_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(text, anchor, '''    QCheckBox* x1_frame_build_attribution_log_checkbox{};
    QCheckBox* x1_gpu_command_attribution_log_checkbox{};
    QCheckBox* x1_gpu_submit_gap_attribution_log_checkbox{};

    const Core::System& system;
''', "GPU-submit widget member")
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
    anchor = '''    x1_gpu_command_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: GPU Command Attribution"), this);

'''
    text = replace_once(text, anchor, anchor + '''    x1_gpu_submit_gap_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: GPU Submit Gap Attribution"), this);

''', "GPU-submit widget construction")

    anchor = '''    x1_gpu_command_attribution_log_checkbox->setToolTip(
        tr("Measure asynchronous GPU worker queue wait/active time plus Scheduler and DmaPusher "
           "command-processing wall time. Observation-only and disabled by default."));

'''
    text = replace_once(text, anchor, anchor + '''    x1_gpu_submit_gap_attribution_log_checkbox->setToolTip(
        tr("Measure time between guest NVDRV GPU submissions and split NVDRV IPC, GPFIFO preparation, "
           "channel lock and PushGPUEntries work. Observation-only and disabled by default."));

''', "GPU-submit tooltip")

    anchor = '''    ui->gridLayout_1->addWidget(x1_gpu_command_attribution_log_checkbox, 9, 2, 1, 2);

'''
    text = replace_once(text, anchor, anchor + '''    ui->gridLayout_1->addWidget(x1_gpu_submit_gap_attribution_log_checkbox, 10, 0, 1, 2);

''', "GPU-submit layout")

    anchor = '''    x1_gpu_command_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_gpu_command_attribution_log_checkbox->setChecked(
        Settings::values.x1_gpu_command_attribution_log.GetValue());
'''
    text = replace_once(text, anchor, anchor + '''    x1_gpu_submit_gap_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_gpu_submit_gap_attribution_log_checkbox->setChecked(
        Settings::values.x1_gpu_submit_gap_attribution_log.GetValue());
''', "GPU-submit widget state")

    anchor = '''    Settings::values.x1_gpu_command_attribution_log =
        x1_gpu_command_attribution_log_checkbox->isChecked();
'''
    text = replace_once(text, anchor, anchor + '''    Settings::values.x1_gpu_submit_gap_attribution_log =
        x1_gpu_submit_gap_attribution_log_checkbox->isChecked();
''', "GPU-submit widget apply")

    anchor = '''    x1_gpu_command_attribution_log_checkbox->setText(
        tr("X1 Log: GPU Command Attribution"));
}
'''
    text = replace_once(text, anchor, '''    x1_gpu_command_attribution_log_checkbox->setText(
        tr("X1 Log: GPU Command Attribution"));
    x1_gpu_submit_gap_attribution_log_checkbox->setText(
        tr("X1 Log: GPU Submit Gap Attribution"));
}
''', "GPU-submit widget retranslate")
    ui_cpp.write_text(text, encoding="utf-8")

    nvdrv_interface = root / "src/core/hle/service/nvdrv/nvdrv_interface.cpp"
    text = nvdrv_interface.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "core/hle/service/nvdrv/nvdrv_interface.h"\n',
        '#include "core/hle/service/nvdrv/nvdrv_interface.h"\n#include "video_core/x1_gpu_submit_profiler.h"\n',
        "NVDRV profiler include")

    anchor = '''void NVDRV::Ioctl1(HLERequestContext& ctx) {
    IPC::RequestParser rp{ctx};
    const auto fd = rp.Pop<DeviceFD>();
    const auto command = rp.PopRaw<Ioctl>();
    LOG_DEBUG(Service_NVDRV, "called fd={}, ioctl={:#08x}", fd, command.raw);

    if (!is_initialized) {
        ServiceError(ctx, NvResult::NotInitialized);
        LOG_ERROR(Service_NVDRV, "NvServices is not initialized!");
        return;
    }

    // Check device
    output_buffer.resize_destructive(ctx.GetWriteBufferSize(0));
    const auto input_buffer = ctx.ReadBuffer(0);

    const auto nv_result = nvdrv->Ioctl1(fd, command, input_buffer, output_buffer);
    if (command.is_out != 0) {
        ctx.WriteBuffer(output_buffer);
    }

    IPC::ResponseBuilder rb{ctx, 3};
    rb.Push(ResultSuccess);
    rb.PushEnum(nv_result);
}
'''
    replacement = '''void NVDRV::Ioctl1(HLERequestContext& ctx) {
    IPC::RequestParser rp{ctx};
    const auto fd = rp.Pop<DeviceFD>();
    const auto command = rp.PopRaw<Ioctl>();
    LOG_DEBUG(Service_NVDRV, "called fd={}, ioctl={:#08x}", fd, command.raw);

    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    const bool x1_submit_log = x1_submit_profiler.Enabled() && command.group == 'H' &&
                               (command.cmd == 0x8 || command.cmd == 0x1b);
    const auto x1_service_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceEntry(1);
    }

    if (!is_initialized) {
        ServiceError(ctx, NvResult::NotInitialized);
        LOG_ERROR(Service_NVDRV, "NvServices is not initialized!");
        return;
    }

    const auto x1_read_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    // Check device
    output_buffer.resize_destructive(ctx.GetWriteBufferSize(0));
    const auto input_buffer = ctx.ReadBuffer(0);
    const u64 x1_read_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_read_start) : 0;

    const auto x1_dispatch_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    const auto nv_result = nvdrv->Ioctl1(fd, command, input_buffer, output_buffer);
    const u64 x1_dispatch_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_dispatch_start) : 0;

    u64 x1_write_ns{};
    if (command.is_out != 0) {
        const auto x1_write_start =
            x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                          : VideoCore::X1GpuSubmitProfiler::TimePoint{};
        ctx.WriteBuffer(output_buffer);
        if (x1_submit_log) {
            x1_write_ns = VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_write_start);
        }
    }

    IPC::ResponseBuilder rb{ctx, 3};
    rb.Push(ResultSuccess);
    rb.PushEnum(nv_result);
    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceCall(
            VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_service_start), x1_read_ns,
            x1_dispatch_ns, x1_write_ns);
    }
}
'''
    text = replace_once(text, anchor, replacement, "NVDRV Ioctl1 attribution")

    anchor = '''void NVDRV::Ioctl2(HLERequestContext& ctx) {
    IPC::RequestParser rp{ctx};
    const auto fd = rp.Pop<DeviceFD>();
    const auto command = rp.PopRaw<Ioctl>();
    LOG_DEBUG(Service_NVDRV, "called fd={}, ioctl={:#08x}", fd, command.raw);

    if (!is_initialized) {
        ServiceError(ctx, NvResult::NotInitialized);
        LOG_ERROR(Service_NVDRV, "NvServices is not initialized!");
        return;
    }

    const auto input_buffer = ctx.ReadBuffer(0);
    const auto input_inlined_buffer = ctx.ReadBuffer(1);
    output_buffer.resize_destructive(ctx.GetWriteBufferSize(0));

    const auto nv_result =
        nvdrv->Ioctl2(fd, command, input_buffer, input_inlined_buffer, output_buffer);
    if (command.is_out != 0) {
        ctx.WriteBuffer(output_buffer);
    }

    IPC::ResponseBuilder rb{ctx, 3};
    rb.Push(ResultSuccess);
    rb.PushEnum(nv_result);
}
'''
    replacement = '''void NVDRV::Ioctl2(HLERequestContext& ctx) {
    IPC::RequestParser rp{ctx};
    const auto fd = rp.Pop<DeviceFD>();
    const auto command = rp.PopRaw<Ioctl>();
    LOG_DEBUG(Service_NVDRV, "called fd={}, ioctl={:#08x}", fd, command.raw);

    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    const bool x1_submit_log = x1_submit_profiler.Enabled() && command.group == 'H' &&
                               command.cmd == 0x1b;
    const auto x1_service_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceEntry(2);
    }

    if (!is_initialized) {
        ServiceError(ctx, NvResult::NotInitialized);
        LOG_ERROR(Service_NVDRV, "NvServices is not initialized!");
        return;
    }

    const auto x1_read_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    const auto input_buffer = ctx.ReadBuffer(0);
    const auto input_inlined_buffer = ctx.ReadBuffer(1);
    output_buffer.resize_destructive(ctx.GetWriteBufferSize(0));
    const u64 x1_read_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_read_start) : 0;

    const auto x1_dispatch_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    const auto nv_result =
        nvdrv->Ioctl2(fd, command, input_buffer, input_inlined_buffer, output_buffer);
    const u64 x1_dispatch_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_dispatch_start) : 0;

    u64 x1_write_ns{};
    if (command.is_out != 0) {
        const auto x1_write_start =
            x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                          : VideoCore::X1GpuSubmitProfiler::TimePoint{};
        ctx.WriteBuffer(output_buffer);
        if (x1_submit_log) {
            x1_write_ns = VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_write_start);
        }
    }

    IPC::ResponseBuilder rb{ctx, 3};
    rb.Push(ResultSuccess);
    rb.PushEnum(nv_result);
    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceCall(
            VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_service_start), x1_read_ns,
            x1_dispatch_ns, x1_write_ns);
    }
}
'''
    text = replace_once(text, anchor, replacement, "NVDRV Ioctl2 attribution")
    nvdrv_interface.write_text(text, encoding="utf-8")

    nvhost = root / "src/core/hle/service/nvdrv/devices/nvhost_gpu.cpp"
    text = nvhost.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/host1x/host1x.h"\n',
        '#include "video_core/host1x/host1x.h"\n#include "video_core/x1_gpu_submit_profiler.h"\n',
        "nvhost_gpu profiler include")

    anchor = '''NvResult nvhost_gpu::Ioctl1(DeviceFD fd, Ioctl command, std::span<const u8> input,
                            std::span<u8> output) {
    switch (command.group) {
'''
    replacement = '''NvResult nvhost_gpu::Ioctl1(DeviceFD fd, Ioctl command, std::span<const u8> input,
                            std::span<u8> output) {
    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    if (x1_submit_profiler.Enabled() && command.group == 'H' &&
        (command.cmd == 0x8 || command.cmd == 0x1b)) {
        x1_submit_profiler.RecordDeviceEntry(1);
    }
    switch (command.group) {
'''
    text = replace_once(text, anchor, replacement, "nvhost Ioctl1 entry")

    anchor = '''NvResult nvhost_gpu::Ioctl2(DeviceFD fd, Ioctl command, std::span<const u8> input,
                            std::span<const u8> inline_input, std::span<u8> output) {
    switch (command.group) {
'''
    replacement = '''NvResult nvhost_gpu::Ioctl2(DeviceFD fd, Ioctl command, std::span<const u8> input,
                            std::span<const u8> inline_input, std::span<u8> output) {
    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    if (x1_submit_profiler.Enabled() && command.group == 'H' && command.cmd == 0x1b) {
        x1_submit_profiler.RecordDeviceEntry(2);
    }
    switch (command.group) {
'''
    text = replace_once(text, anchor, replacement, "nvhost Ioctl2 entry")

    anchor = '''NvResult nvhost_gpu::SubmitGPFIFOImpl(IoctlSubmitGpfifo& params, Tegra::CommandList&& entries) {
    LOG_TRACE(Service_NVDRV, "called, gpfifo={:X}, num_entries={:X}, flags={:X}", params.address,
              params.num_entries, params.flags.raw);

    auto& gpu = system.GPU();

    std::scoped_lock lock(channel_mutex);

    // Lazily initialize channel when address space is available
    if (!channel_state->initialized && channel_state->memory_manager) {
        system.GPU().InitChannel(*channel_state, channel_state->program_id);
    }

    const auto bind_id = channel_state->bind_id;

    auto& flags = params.flags;

    if (flags.fence_wait.Value()) {
        if (flags.increment_value.Value()) {
            return NvResult::BadParameter;
        }

        if (!syncpoint_manager.IsFenceSignalled(params.fence)) {
            gpu.PushGPUEntries(bind_id, Tegra::CommandList{BuildWaitCommandList(params.fence)});
        }
    }

    params.fence.id = channel_syncpoint;

    u32 increment{(flags.fence_increment.Value() != 0 ? 2 : 0) +
                  (flags.increment_value.Value() != 0 ? params.fence.value : 0)};
    params.fence.value = syncpoint_manager.IncrementSyncpointMaxExt(channel_syncpoint, increment);
    gpu.PushGPUEntries(bind_id, std::move(entries));

    if (flags.fence_increment.Value()) {
        if (flags.suppress_wfi.Value()) {
            gpu.PushGPUEntries(bind_id,
                               Tegra::CommandList{BuildIncrementCommandList(params.fence)});
        } else {
            gpu.PushGPUEntries(bind_id,
                               Tegra::CommandList{BuildIncrementWithWfiCommandList(params.fence)});
        }
    }

    flags.raw = 0;

    return NvResult::Success;
}
'''
    replacement = '''NvResult nvhost_gpu::SubmitGPFIFOImpl(IoctlSubmitGpfifo& params, Tegra::CommandList&& entries) {
    LOG_TRACE(Service_NVDRV, "called, gpfifo={:X}, num_entries={:X}, flags={:X}", params.address,
              params.num_entries, params.flags.raw);

    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    const bool x1_submit_log = x1_submit_profiler.Enabled();
    const auto x1_impl_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    auto& gpu = system.GPU();

    const auto x1_lock_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    std::scoped_lock lock(channel_mutex);
    const u64 x1_lock_wait_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_lock_start) : 0;

    u64 x1_init_ns{};
    if (!channel_state->initialized && channel_state->memory_manager) {
        const auto x1_init_start =
            x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                          : VideoCore::X1GpuSubmitProfiler::TimePoint{};
        system.GPU().InitChannel(*channel_state, channel_state->program_id);
        if (x1_submit_log) {
            x1_init_ns = VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_init_start);
        }
    }

    const auto bind_id = channel_state->bind_id;
    auto& flags = params.flags;

    u64 x1_fence_check_ns{};
    u64 x1_wait_push_ns{};
    if (flags.fence_wait.Value()) {
        if (flags.increment_value.Value()) {
            return NvResult::BadParameter;
        }

        const auto x1_fence_start =
            x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                          : VideoCore::X1GpuSubmitProfiler::TimePoint{};
        const bool x1_needs_wait = !syncpoint_manager.IsFenceSignalled(params.fence);
        if (x1_submit_log) {
            x1_fence_check_ns = VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_fence_start);
        }
        if (x1_needs_wait) {
            if (x1_submit_log) x1_submit_profiler.RecordSubmitPushEntry(0);
            const auto x1_push_start =
                x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                              : VideoCore::X1GpuSubmitProfiler::TimePoint{};
            gpu.PushGPUEntries(bind_id, Tegra::CommandList{BuildWaitCommandList(params.fence)});
            if (x1_submit_log) {
                x1_wait_push_ns = VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_push_start);
            }
        }
    }

    const auto x1_sync_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    params.fence.id = channel_syncpoint;
    u32 increment{(flags.fence_increment.Value() != 0 ? 2 : 0) +
                  (flags.increment_value.Value() != 0 ? params.fence.value : 0)};
    params.fence.value = syncpoint_manager.IncrementSyncpointMaxExt(channel_syncpoint, increment);
    const u64 x1_syncpoint_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_sync_start) : 0;

    if (x1_submit_log) x1_submit_profiler.RecordSubmitPushEntry(1);
    const auto x1_main_push_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    gpu.PushGPUEntries(bind_id, std::move(entries));
    const u64 x1_main_push_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_main_push_start) : 0;

    u64 x1_fence_push_ns{};
    if (flags.fence_increment.Value()) {
        if (x1_submit_log) x1_submit_profiler.RecordSubmitPushEntry(2);
        const auto x1_push_start =
            x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                          : VideoCore::X1GpuSubmitProfiler::TimePoint{};
        if (flags.suppress_wfi.Value()) {
            gpu.PushGPUEntries(bind_id,
                               Tegra::CommandList{BuildIncrementCommandList(params.fence)});
        } else {
            gpu.PushGPUEntries(bind_id,
                               Tegra::CommandList{BuildIncrementWithWfiCommandList(params.fence)});
        }
        if (x1_submit_log) {
            x1_fence_push_ns = VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_push_start);
        }
    }

    flags.raw = 0;
    if (x1_submit_log) {
        x1_submit_profiler.RecordImpl(
            VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_impl_start), x1_lock_wait_ns,
            x1_init_ns, x1_fence_check_ns, x1_syncpoint_ns, x1_wait_push_ns,
            x1_main_push_ns, x1_fence_push_ns);
    }
    return NvResult::Success;
}
'''
    text = replace_once(text, anchor, replacement, "SubmitGPFIFOImpl attribution")

    anchor = '''NvResult nvhost_gpu::SubmitGPFIFOBase1(IoctlSubmitGpfifo& params,
                                       std::span<Tegra::CommandListHeader> commands, bool kickoff) {
    if (params.num_entries > commands.size()) {
        UNIMPLEMENTED();
        return NvResult::InvalidSize;
    }

    Tegra::CommandList entries(params.num_entries);
    if (kickoff) {
        system.ApplicationMemory().ReadBlock(params.address, entries.command_lists.data(),
                                             params.num_entries * sizeof(Tegra::CommandListHeader));
    } else {
        std::memcpy(entries.command_lists.data(), commands.data(),
                    params.num_entries * sizeof(Tegra::CommandListHeader));
    }

    return SubmitGPFIFOImpl(params, std::move(entries));
}
'''
    replacement = '''NvResult nvhost_gpu::SubmitGPFIFOBase1(IoctlSubmitGpfifo& params,
                                       std::span<Tegra::CommandListHeader> commands, bool kickoff) {
    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    const bool x1_submit_log = x1_submit_profiler.Enabled();
    const auto x1_base_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    if (params.num_entries > commands.size()) {
        UNIMPLEMENTED();
        return NvResult::InvalidSize;
    }

    const auto x1_alloc_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    Tegra::CommandList entries(params.num_entries);
    const u64 x1_alloc_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_alloc_start) : 0;

    const auto x1_copy_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    if (kickoff) {
        system.ApplicationMemory().ReadBlock(params.address, entries.command_lists.data(),
                                             params.num_entries * sizeof(Tegra::CommandListHeader));
    } else {
        std::memcpy(entries.command_lists.data(), commands.data(),
                    params.num_entries * sizeof(Tegra::CommandListHeader));
    }
    const u64 x1_copy_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_copy_start) : 0;

    const auto result = SubmitGPFIFOImpl(params, std::move(entries));
    if (x1_submit_log) {
        x1_submit_profiler.RecordBase(
            VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_base_start), x1_alloc_ns, x1_copy_ns,
            params.num_entries, 1);
    }
    return result;
}
'''
    text = replace_once(text, anchor, replacement, "SubmitGPFIFOBase1 attribution")

    anchor = '''NvResult nvhost_gpu::SubmitGPFIFOBase2(IoctlSubmitGpfifo& params,
                                       std::span<const Tegra::CommandListHeader> commands) {
    if (params.num_entries > commands.size()) {
        UNIMPLEMENTED();
        return NvResult::InvalidSize;
    }

    Tegra::CommandList entries(params.num_entries);
    std::memcpy(entries.command_lists.data(), commands.data(),
                params.num_entries * sizeof(Tegra::CommandListHeader));
    return SubmitGPFIFOImpl(params, std::move(entries));
}
'''
    replacement = '''NvResult nvhost_gpu::SubmitGPFIFOBase2(IoctlSubmitGpfifo& params,
                                       std::span<const Tegra::CommandListHeader> commands) {
    auto& x1_submit_profiler = VideoCore::X1GpuSubmitProfiler::Get();
    const bool x1_submit_log = x1_submit_profiler.Enabled();
    const auto x1_base_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    if (params.num_entries > commands.size()) {
        UNIMPLEMENTED();
        return NvResult::InvalidSize;
    }

    const auto x1_alloc_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    Tegra::CommandList entries(params.num_entries);
    const u64 x1_alloc_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_alloc_start) : 0;

    const auto x1_copy_start =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::Now()
                      : VideoCore::X1GpuSubmitProfiler::TimePoint{};
    std::memcpy(entries.command_lists.data(), commands.data(),
                params.num_entries * sizeof(Tegra::CommandListHeader));
    const u64 x1_copy_ns =
        x1_submit_log ? VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_copy_start) : 0;

    const auto result = SubmitGPFIFOImpl(params, std::move(entries));
    if (x1_submit_log) {
        x1_submit_profiler.RecordBase(
            VideoCore::X1GpuSubmitProfiler::ElapsedNs(x1_base_start), x1_alloc_ns, x1_copy_ns,
            params.num_entries, 2);
    }
    return result;
}
'''
    text = replace_once(text, anchor, replacement, "SubmitGPFIFOBase2 attribution")
    nvhost.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/x1_gpu_command_profiler.h"\n',
        '#include "video_core/x1_gpu_command_profiler.h"\n#include "video_core/x1_gpu_submit_profiler.h"\n',
        "rasterizer submit profiler include")

    anchor = '''    VideoCore::X1GpuCommandProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(text, anchor, '''    VideoCore::X1GpuCommandProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    VideoCore::X1GpuSubmitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
''', "submit profiler initialization")

    anchor = '''    VideoCore::X1GpuCommandProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(text, anchor, '''    VideoCore::X1GpuCommandProfiler::Get().FrameEnd();
    VideoCore::X1GpuSubmitProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
''', "submit profiler frame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        settings: ["x1_gpu_submit_gap_attribution_log"],
        ui_cpp: ["X1 Log: GPU Submit Gap Attribution"],
        nvdrv_interface: ["RecordServiceEntry", "RecordServiceCall"],
        nvhost: ["RecordDeviceEntry", "RecordBase", "RecordSubmitPushEntry", "RecordImpl"],
        rasterizer: ["X1GpuSubmitProfiler::Get().Initialize", "X1GpuSubmitProfiler::Get().FrameEnd"],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    print("Transplanted exact dc95 X1 GPU submission-gap attribution over GPU-command harness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
