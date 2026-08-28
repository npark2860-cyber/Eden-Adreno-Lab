#!/usr/bin/env python3
"""Add observation-only NVDRV sync-IPC dispatch-gap attribution over the guest-submit harness."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_nvdrv_ipc_dispatch_gap.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_nvdrv_ipc_dispatch_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_nvdrv_ipc_dispatch_profiler.h must be copied before this pass")

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_guest_submit_thread_attribution_log{
        linkage, false, "x1_guest_submit_thread_attribution_log", Category::Debugging};
'''
    text = replace_once(
        text, anchor,
        anchor + '''    Setting<bool> x1_nvdrv_ipc_dispatch_gap_log{
        linkage, false, "x1_nvdrv_ipc_dispatch_gap_log", Category::Debugging};
''',
        "ipc-dispatch setting")
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_gpu_submit_gap_attribution_log_checkbox{};
    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(
        text, anchor,
        '''    QCheckBox* x1_gpu_submit_gap_attribution_log_checkbox{};
    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};
    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};

    const Core::System& system;
''',
        "ipc-dispatch widget member")
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")

    anchor = '''    x1_guest_submit_thread_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Guest Submit Thread Attribution"), this);

'''
    text = replace_once(
        text, anchor,
        anchor + '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox =
        new QCheckBox(tr("X1 Log: NVDRV IPC Dispatch Gap"), this);

''',
        "ipc-dispatch widget construction")

    anchor = '''    x1_guest_submit_thread_attribution_log_checkbox->setToolTip(
        tr("Identify the guest thread issuing GPU submit ioctls and compare its scheduled CPU ticks "
           "against elapsed guest ticks between submissions. Observation-only and disabled by default."));

'''
    text = replace_once(
        text, anchor,
        anchor + '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setToolTip(
        tr("Split the dominant GPU-submit cycle into guest post-reply, synchronous IPC dispatch, "
           "and NVDRV handler/reply time. Observation-only and disabled by default."));

''',
        "ipc-dispatch tooltip")

    anchor = '''    ui->gridLayout_1->addWidget(x1_guest_submit_thread_attribution_log_checkbox, 10, 2, 1, 2);

'''
    text = replace_once(
        text, anchor,
        anchor + '''    ui->gridLayout_1->addWidget(x1_nvdrv_ipc_dispatch_gap_log_checkbox, 11, 0, 1, 2);

''',
        "ipc-dispatch layout")

    anchor = '''    x1_guest_submit_thread_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_guest_submit_thread_attribution_log_checkbox->setChecked(
        Settings::values.x1_guest_submit_thread_attribution_log.GetValue());
'''
    text = replace_once(
        text, anchor,
        anchor + '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setEnabled(runtime_lock);
    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setChecked(
        Settings::values.x1_nvdrv_ipc_dispatch_gap_log.GetValue());
''',
        "ipc-dispatch widget state")

    anchor = '''    Settings::values.x1_guest_submit_thread_attribution_log =
        x1_guest_submit_thread_attribution_log_checkbox->isChecked();
'''
    text = replace_once(
        text, anchor,
        anchor + '''    Settings::values.x1_nvdrv_ipc_dispatch_gap_log =
        x1_nvdrv_ipc_dispatch_gap_log_checkbox->isChecked();
''',
        "ipc-dispatch widget apply")

    anchor = '''    x1_guest_submit_thread_attribution_log_checkbox->setText(
        tr("X1 Log: Guest Submit Thread Attribution"));
}
'''
    text = replace_once(
        text, anchor,
        '''    x1_guest_submit_thread_attribution_log_checkbox->setText(
        tr("X1 Log: Guest Submit Thread Attribution"));
    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setText(
        tr("X1 Log: NVDRV IPC Dispatch Gap"));
}
''',
        "ipc-dispatch widget retranslate")
    ui_cpp.write_text(text, encoding="utf-8")

    svc_ipc = root / "src/core/hle/kernel/svc/svc_ipc.cpp"
    text = svc_ipc.read_text(encoding="utf-8")
    text = replace_once(
        text, '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n',
        "ipc-dispatch profiler include in svc_ipc")
    text = replace_once(
        text, '#include "core/hle/kernel/k_session.h"\n',
        '#include "core/hle/kernel/k_session.h"\n#include "core/hle/kernel/k_thread.h"\n',
        "ipc-dispatch thread include in svc_ipc")
    anchor = '''    // Send the request.
    R_RETURN(session->SendSyncRequest(kernel, message, buffer_size));
'''
    replacement = '''    // Record the exact generic synchronous-IPC entry before the request can block.
    auto& x1_ipc_dispatch_profiler = Core::X1NvdrvIpcDispatchProfiler::Get();
    if (x1_ipc_dispatch_profiler.Enabled()) {
        x1_ipc_dispatch_profiler.RecordSyncRequestEntry(GetCurrentThread(kernel).GetThreadId());
    }

    // Send the request.
    R_RETURN(session->SendSyncRequest(kernel, message, buffer_size));
'''
    text = replace_once(text, anchor, replacement, "generic sync-request entry")
    svc_ipc.write_text(text, encoding="utf-8")

    nvdrv = root / "src/core/hle/service/nvdrv/nvdrv_interface.cpp"
    text = nvdrv.read_text(encoding="utf-8")
    text = replace_once(
        text, '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n',
        "ipc-dispatch profiler include in nvdrv")

    anchor = '''    if (x1_guest_submit_log) {
        auto& x1_thread = ctx.GetThread();
        x1_guest_submit_profiler.RecordSubmitCaller(
            x1_thread.GetThreadId(), x1_thread.GetCpuTime(), system.CoreTiming().GetClockTicks(),
            x1_thread.GetContext().pc, x1_thread.GetCurrentCore(), x1_thread.GetActiveCore(),
            x1_thread.GetPriority(), 1);
    }

    if (!is_initialized) {
'''
    replacement = '''    if (x1_guest_submit_log) {
        auto& x1_thread = ctx.GetThread();
        x1_guest_submit_profiler.RecordSubmitCaller(
            x1_thread.GetThreadId(), x1_thread.GetCpuTime(), system.CoreTiming().GetClockTicks(),
            x1_thread.GetContext().pc, x1_thread.GetCurrentCore(), x1_thread.GetActiveCore(),
            x1_thread.GetPriority(), 1);
    }

    auto& x1_ipc_dispatch_profiler = Core::X1NvdrvIpcDispatchProfiler::Get();
    const bool x1_ipc_dispatch_log = x1_ipc_dispatch_profiler.Enabled() &&
                                     command.group == 'H' &&
                                     (command.cmd == 0x8 || command.cmd == 0x1b);
    const u64 x1_ipc_dispatch_tid =
        x1_ipc_dispatch_log ? ctx.GetThread().GetThreadId() : 0;
    if (x1_ipc_dispatch_log) {
        x1_ipc_dispatch_profiler.RecordNvdrvHandlerEntry(x1_ipc_dispatch_tid, 1);
    }
    SCOPE_EXIT {
        if (x1_ipc_dispatch_log) {
            x1_ipc_dispatch_profiler.RecordNvdrvHandlerComplete(x1_ipc_dispatch_tid);
        }
    };

    if (!is_initialized) {
'''
    text = replace_once(text, anchor, replacement, "Ioctl1 ipc-dispatch boundaries")

    anchor = '''    if (x1_guest_submit_log) {
        auto& x1_thread = ctx.GetThread();
        x1_guest_submit_profiler.RecordSubmitCaller(
            x1_thread.GetThreadId(), x1_thread.GetCpuTime(), system.CoreTiming().GetClockTicks(),
            x1_thread.GetContext().pc, x1_thread.GetCurrentCore(), x1_thread.GetActiveCore(),
            x1_thread.GetPriority(), 2);
    }

    if (!is_initialized) {
'''
    replacement = '''    if (x1_guest_submit_log) {
        auto& x1_thread = ctx.GetThread();
        x1_guest_submit_profiler.RecordSubmitCaller(
            x1_thread.GetThreadId(), x1_thread.GetCpuTime(), system.CoreTiming().GetClockTicks(),
            x1_thread.GetContext().pc, x1_thread.GetCurrentCore(), x1_thread.GetActiveCore(),
            x1_thread.GetPriority(), 2);
    }

    auto& x1_ipc_dispatch_profiler = Core::X1NvdrvIpcDispatchProfiler::Get();
    const bool x1_ipc_dispatch_log = x1_ipc_dispatch_profiler.Enabled() &&
                                     command.group == 'H' && command.cmd == 0x1b;
    const u64 x1_ipc_dispatch_tid =
        x1_ipc_dispatch_log ? ctx.GetThread().GetThreadId() : 0;
    if (x1_ipc_dispatch_log) {
        x1_ipc_dispatch_profiler.RecordNvdrvHandlerEntry(x1_ipc_dispatch_tid, 2);
    }
    SCOPE_EXIT {
        if (x1_ipc_dispatch_log) {
            x1_ipc_dispatch_profiler.RecordNvdrvHandlerComplete(x1_ipc_dispatch_tid);
        }
    };

    if (!is_initialized) {
'''
    text = replace_once(text, anchor, replacement, "Ioctl2 ipc-dispatch boundaries")
    nvdrv.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text, '#include "video_core/x1_guest_submit_profiler.h"\n',
        '#include "video_core/x1_guest_submit_profiler.h"\n#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n',
        "rasterizer ipc-dispatch include")

    anchor = '''    VideoCore::X1GuestSubmitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(
        text, anchor,
        '''    VideoCore::X1GuestSubmitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    Core::X1NvdrvIpcDispatchProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
''',
        "ipc-dispatch initialization")

    anchor = '''    VideoCore::X1GuestSubmitProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(
        text, anchor,
        '''    VideoCore::X1GuestSubmitProfiler::Get().FrameEnd();
    Core::X1NvdrvIpcDispatchProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
''',
        "ipc-dispatch frame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        settings: ["x1_nvdrv_ipc_dispatch_gap_log"],
        ui_cpp: ["X1 Log: NVDRV IPC Dispatch Gap"],
        svc_ipc: ["RecordSyncRequestEntry", "GetThreadId()"],
        nvdrv: ["RecordNvdrvHandlerEntry", "RecordNvdrvHandlerComplete"],
        rasterizer: [
            "X1NvdrvIpcDispatchProfiler::Get().Initialize",
            "X1NvdrvIpcDispatchProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    print("Transplanted exact dc95 X1 NVDRV IPC dispatch-gap attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
