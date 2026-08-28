#!/usr/bin/env python3
"""Add observation-only guest submitter thread attribution over the GPU-submit harness."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_guest_submit_thread_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/video_core/x1_guest_submit_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_guest_submit_profiler.h must be copied before this pass")

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_gpu_submit_gap_attribution_log{
        linkage, false, "x1_gpu_submit_gap_attribution_log", Category::Debugging};
'''
    text = replace_once(text, anchor, anchor + '''    Setting<bool> x1_guest_submit_thread_attribution_log{
        linkage, false, "x1_guest_submit_thread_attribution_log", Category::Debugging};
''', "guest-submit setting")
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_gpu_command_attribution_log_checkbox{};
    QCheckBox* x1_gpu_submit_gap_attribution_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(text, anchor, '''    QCheckBox* x1_gpu_command_attribution_log_checkbox{};
    QCheckBox* x1_gpu_submit_gap_attribution_log_checkbox{};
    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};

    const Core::System& system;
''', "guest-submit widget member")
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
    anchor = '''    x1_gpu_submit_gap_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: GPU Submit Gap Attribution"), this);

'''
    text = replace_once(text, anchor, anchor + '''    x1_guest_submit_thread_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Guest Submit Thread Attribution"), this);

''', "guest-submit widget construction")

    anchor = '''    x1_gpu_submit_gap_attribution_log_checkbox->setToolTip(
        tr("Measure time between guest NVDRV GPU submissions and split NVDRV IPC, GPFIFO preparation, "
           "channel lock and PushGPUEntries work. Observation-only and disabled by default."));

'''
    text = replace_once(text, anchor, anchor + '''    x1_guest_submit_thread_attribution_log_checkbox->setToolTip(
        tr("Identify the guest thread issuing GPU submit ioctls and compare its scheduled CPU ticks "
           "against elapsed guest ticks between submissions. Observation-only and disabled by default."));

''', "guest-submit tooltip")

    anchor = '''    ui->gridLayout_1->addWidget(x1_gpu_submit_gap_attribution_log_checkbox, 10, 0, 1, 2);

'''
    text = replace_once(text, anchor, anchor + '''    ui->gridLayout_1->addWidget(x1_guest_submit_thread_attribution_log_checkbox, 10, 2, 1, 2);

''', "guest-submit layout")

    anchor = '''    x1_gpu_submit_gap_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_gpu_submit_gap_attribution_log_checkbox->setChecked(
        Settings::values.x1_gpu_submit_gap_attribution_log.GetValue());
'''
    text = replace_once(text, anchor, anchor + '''    x1_guest_submit_thread_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_guest_submit_thread_attribution_log_checkbox->setChecked(
        Settings::values.x1_guest_submit_thread_attribution_log.GetValue());
''', "guest-submit widget state")

    anchor = '''    Settings::values.x1_gpu_submit_gap_attribution_log =
        x1_gpu_submit_gap_attribution_log_checkbox->isChecked();
'''
    text = replace_once(text, anchor, anchor + '''    Settings::values.x1_guest_submit_thread_attribution_log =
        x1_guest_submit_thread_attribution_log_checkbox->isChecked();
''', "guest-submit widget apply")

    anchor = '''    x1_gpu_submit_gap_attribution_log_checkbox->setText(
        tr("X1 Log: GPU Submit Gap Attribution"));
}
'''
    text = replace_once(text, anchor, '''    x1_gpu_submit_gap_attribution_log_checkbox->setText(
        tr("X1 Log: GPU Submit Gap Attribution"));
    x1_guest_submit_thread_attribution_log_checkbox->setText(
        tr("X1 Log: Guest Submit Thread Attribution"));
}
''', "guest-submit widget retranslate")
    ui_cpp.write_text(text, encoding="utf-8")

    nvdrv = root / "src/core/hle/service/nvdrv/nvdrv_interface.cpp"
    text = nvdrv.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/core_timing.h"\n#include "core/hle/kernel/k_thread.h"\n',
        "guest-submit kernel includes")
    text = replace_once(text,
        '#include "video_core/x1_gpu_submit_profiler.h"\n',
        '#include "video_core/x1_gpu_submit_profiler.h"\n#include "video_core/x1_guest_submit_profiler.h"\n',
        "guest-submit profiler include")

    anchor = '''    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceEntry(1);
    }

    if (!is_initialized) {
'''
    replacement = '''    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceEntry(1);
    }
    auto& x1_guest_submit_profiler = VideoCore::X1GuestSubmitProfiler::Get();
    const bool x1_guest_submit_log = x1_guest_submit_profiler.Enabled() &&
                                     command.group == 'H' &&
                                     (command.cmd == 0x8 || command.cmd == 0x1b);
    if (x1_guest_submit_log) {
        auto& x1_thread = ctx.GetThread();
        x1_guest_submit_profiler.RecordSubmitCaller(
            x1_thread.GetThreadId(), x1_thread.GetCpuTime(), system.CoreTiming().GetClockTicks(),
            x1_thread.GetContext().pc, x1_thread.GetCurrentCore(), x1_thread.GetActiveCore(),
            x1_thread.GetPriority(), 1);
    }

    if (!is_initialized) {
'''
    text = replace_once(text, anchor, replacement, "Ioctl1 guest submit caller")

    anchor = '''    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceEntry(2);
    }

    if (!is_initialized) {
'''
    replacement = '''    if (x1_submit_log) {
        x1_submit_profiler.RecordServiceEntry(2);
    }
    auto& x1_guest_submit_profiler = VideoCore::X1GuestSubmitProfiler::Get();
    const bool x1_guest_submit_log = x1_guest_submit_profiler.Enabled() &&
                                     command.group == 'H' && command.cmd == 0x1b;
    if (x1_guest_submit_log) {
        auto& x1_thread = ctx.GetThread();
        x1_guest_submit_profiler.RecordSubmitCaller(
            x1_thread.GetThreadId(), x1_thread.GetCpuTime(), system.CoreTiming().GetClockTicks(),
            x1_thread.GetContext().pc, x1_thread.GetCurrentCore(), x1_thread.GetActiveCore(),
            x1_thread.GetPriority(), 2);
    }

    if (!is_initialized) {
'''
    text = replace_once(text, anchor, replacement, "Ioctl2 guest submit caller")
    nvdrv.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(text,
        '#include "video_core/x1_gpu_submit_profiler.h"\n',
        '#include "video_core/x1_gpu_submit_profiler.h"\n#include "video_core/x1_guest_submit_profiler.h"\n',
        "rasterizer guest-submit include")

    anchor = '''    VideoCore::X1GpuSubmitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(text, anchor, '''    VideoCore::X1GpuSubmitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    VideoCore::X1GuestSubmitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
''', "guest-submit initialization")

    anchor = '''    VideoCore::X1GpuSubmitProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(text, anchor, '''    VideoCore::X1GpuSubmitProfiler::Get().FrameEnd();
    VideoCore::X1GuestSubmitProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
''', "guest-submit frame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        settings: ["x1_guest_submit_thread_attribution_log"],
        ui_cpp: ["X1 Log: Guest Submit Thread Attribution"],
        nvdrv: ["RecordSubmitCaller", "GetCpuTime()", "GetClockTicks()", "GetContext().pc"],
        rasterizer: ["X1GuestSubmitProfiler::Get().Initialize", "X1GuestSubmitProfiler::Get().FrameEnd"],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    print("Transplanted exact dc95 X1 guest submit-thread attribution over GPU-submit harness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
