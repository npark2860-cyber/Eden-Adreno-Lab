#!/usr/bin/env python3
"""Add observation-only guest post-submit wait attribution over the IPC-dispatch harness."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_guest_post_wait_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_guest_post_wait_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_guest_post_wait_profiler.h must be copied before this pass")

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_nvdrv_ipc_dispatch_gap_log{
        linkage, false, "x1_nvdrv_ipc_dispatch_gap_log", Category::Debugging};
'''
    text = replace_once(
        text, anchor,
        anchor + '''    Setting<bool> x1_guest_post_wait_attribution_log{
        linkage, false, "x1_guest_post_wait_attribution_log", Category::Debugging};
''',
        "guest-post-wait setting")
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};
    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(
        text, anchor,
        '''    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};
    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};
    QCheckBox* x1_guest_post_wait_attribution_log_checkbox{};

    const Core::System& system;
''',
        "guest-post-wait widget member")
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
    anchor = '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox =
        new QCheckBox(tr("X1 Log: NVDRV IPC Dispatch Gap"), this);

'''
    text = replace_once(
        text, anchor,
        anchor + '''    x1_guest_post_wait_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Guest Post Wait Attribution"), this);

''',
        "guest-post-wait widget construction")

    anchor = '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setToolTip(
        tr("Split the dominant GPU-submit cycle into guest post-reply, synchronous IPC dispatch, "
           "and NVDRV handler/reply time. Observation-only and disabled by default."));

'''
    text = replace_once(
        text, anchor,
        anchor + '''    x1_guest_post_wait_attribution_log_checkbox->setToolTip(
        tr("Attribute the dominant submitter's post-NVDRV interval by KThread wait reason and SVC, "
           "and report the remaining runnable/CPU residual. Observation-only and disabled by default."));

''',
        "guest-post-wait tooltip")

    anchor = '''    ui->gridLayout_1->addWidget(x1_nvdrv_ipc_dispatch_gap_log_checkbox, 11, 0, 1, 2);

'''
    text = replace_once(
        text, anchor,
        anchor + '''    ui->gridLayout_1->addWidget(x1_guest_post_wait_attribution_log_checkbox, 11, 2, 1, 2);

''',
        "guest-post-wait layout")

    anchor = '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setEnabled(runtime_lock);
    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setChecked(
        Settings::values.x1_nvdrv_ipc_dispatch_gap_log.GetValue());
'''
    text = replace_once(
        text, anchor,
        anchor + '''    x1_guest_post_wait_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_guest_post_wait_attribution_log_checkbox->setChecked(
        Settings::values.x1_guest_post_wait_attribution_log.GetValue());
''',
        "guest-post-wait widget state")

    anchor = '''    Settings::values.x1_nvdrv_ipc_dispatch_gap_log =
        x1_nvdrv_ipc_dispatch_gap_log_checkbox->isChecked();
'''
    text = replace_once(
        text, anchor,
        anchor + '''    Settings::values.x1_guest_post_wait_attribution_log =
        x1_guest_post_wait_attribution_log_checkbox->isChecked();
''',
        "guest-post-wait widget apply")

    anchor = '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setText(
        tr("X1 Log: NVDRV IPC Dispatch Gap"));
}
'''
    text = replace_once(
        text, anchor,
        '''    x1_nvdrv_ipc_dispatch_gap_log_checkbox->setText(
        tr("X1 Log: NVDRV IPC Dispatch Gap"));
    x1_guest_post_wait_attribution_log_checkbox->setText(
        tr("X1 Log: Guest Post Wait Attribution"));
}
''',
        "guest-post-wait widget retranslate")
    ui_cpp.write_text(text, encoding="utf-8")

    kthread = root / "src/core/hle/kernel/k_thread.cpp"
    text = kthread.read_text(encoding="utf-8")
    text = replace_once(
        text, '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_guest_post_wait_profiler.h"\n',
        "guest-post-wait include in k_thread")

    anchor = '''    void KThread::SetState(KernelCore& kernel, ThreadState state) {
        KScopedSchedulerLock sl{kernel};
        // Clear debugging state
        this->SetWaitReasonForDebugging({});
        const ThreadState old_state = m_thread_state.load(std::memory_order_relaxed);
        m_thread_state.store(
            static_cast<ThreadState>((old_state & ~ThreadState::Mask) | (state & ThreadState::Mask)),
            std::memory_order_relaxed);
        if (m_thread_state.load(std::memory_order_relaxed) != old_state) {
            KScheduler::OnThreadStateChanged(kernel, this, old_state);
        }
'''
    replacement = '''    void KThread::SetState(KernelCore& kernel, ThreadState state) {
        KScopedSchedulerLock sl{kernel};
        auto& x1_guest_wait_profiler = Core::X1GuestPostWaitProfiler::Get();
        const bool x1_guest_wait_log = x1_guest_wait_profiler.Enabled();
        const ThreadState x1_old_base_state =
            x1_guest_wait_log ? this->GetState() : ThreadState::Initialized;
        const auto x1_old_wait_reason =
            x1_guest_wait_log ? this->GetWaitReasonForDebugging() : ThreadWaitReasonForDebugging::None;
        const u8 x1_current_svc_id =
            x1_guest_wait_log ? this->GetStackParameters().current_svc_id : 0;

        // Clear debugging state
        this->SetWaitReasonForDebugging({});
        const ThreadState old_state = m_thread_state.load(std::memory_order_relaxed);
        m_thread_state.store(
            static_cast<ThreadState>((old_state & ~ThreadState::Mask) | (state & ThreadState::Mask)),
            std::memory_order_relaxed);
        if (x1_guest_wait_log) {
            x1_guest_wait_profiler.RecordThreadStateTransition(
                this->GetThreadId(), static_cast<u32>(x1_old_base_state),
                static_cast<u32>(state & ThreadState::Mask), static_cast<u32>(x1_old_wait_reason),
                x1_current_svc_id);
        }
        if (m_thread_state.load(std::memory_order_relaxed) != old_state) {
            KScheduler::OnThreadStateChanged(kernel, this, old_state);
        }
'''
    text = replace_once(text, anchor, replacement, "KThread wait-state transition attribution")
    kthread.write_text(text, encoding="utf-8")

    nvdrv = root / "src/core/hle/service/nvdrv/nvdrv_interface.cpp"
    text = nvdrv.read_text(encoding="utf-8")
    text = replace_once(
        text, '#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n',
        '#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n#include "core/x1_guest_post_wait_profiler.h"\n',
        "guest-post-wait include in nvdrv")

    anchor = '''    if (x1_ipc_dispatch_log) {
        x1_ipc_dispatch_profiler.RecordNvdrvHandlerEntry(x1_ipc_dispatch_tid, 1);
    }
    SCOPE_EXIT {
        if (x1_ipc_dispatch_log) {
            x1_ipc_dispatch_profiler.RecordNvdrvHandlerComplete(x1_ipc_dispatch_tid);
        }
    };

    if (!is_initialized) {
'''
    replacement = '''    if (x1_ipc_dispatch_log) {
        x1_ipc_dispatch_profiler.RecordNvdrvHandlerEntry(x1_ipc_dispatch_tid, 1);
    }

    auto& x1_guest_wait_profiler = Core::X1GuestPostWaitProfiler::Get();
    const bool x1_guest_wait_log = x1_guest_wait_profiler.Enabled() &&
                                   command.group == 'H' &&
                                   (command.cmd == 0x8 || command.cmd == 0x1b);
    const u64 x1_guest_wait_tid = x1_guest_wait_log ? ctx.GetThread().GetThreadId() : 0;
    if (x1_guest_wait_log) {
        x1_guest_wait_profiler.RecordCandidateHandlerEntry(x1_guest_wait_tid);
    }
    SCOPE_EXIT {
        if (x1_ipc_dispatch_log) {
            x1_ipc_dispatch_profiler.RecordNvdrvHandlerComplete(x1_ipc_dispatch_tid);
        }
        if (x1_guest_wait_log) {
            x1_guest_wait_profiler.RecordCandidateHandlerComplete(x1_guest_wait_tid);
        }
    };

    if (!is_initialized) {
'''
    text = replace_once(text, anchor, replacement, "Ioctl1 guest-post-wait boundaries")

    anchor = '''    if (x1_ipc_dispatch_log) {
        x1_ipc_dispatch_profiler.RecordNvdrvHandlerEntry(x1_ipc_dispatch_tid, 2);
    }
    SCOPE_EXIT {
        if (x1_ipc_dispatch_log) {
            x1_ipc_dispatch_profiler.RecordNvdrvHandlerComplete(x1_ipc_dispatch_tid);
        }
    };

    if (!is_initialized) {
'''
    replacement = '''    if (x1_ipc_dispatch_log) {
        x1_ipc_dispatch_profiler.RecordNvdrvHandlerEntry(x1_ipc_dispatch_tid, 2);
    }

    auto& x1_guest_wait_profiler = Core::X1GuestPostWaitProfiler::Get();
    const bool x1_guest_wait_log = x1_guest_wait_profiler.Enabled() &&
                                   command.group == 'H' && command.cmd == 0x1b;
    const u64 x1_guest_wait_tid = x1_guest_wait_log ? ctx.GetThread().GetThreadId() : 0;
    if (x1_guest_wait_log) {
        x1_guest_wait_profiler.RecordCandidateHandlerEntry(x1_guest_wait_tid);
    }
    SCOPE_EXIT {
        if (x1_ipc_dispatch_log) {
            x1_ipc_dispatch_profiler.RecordNvdrvHandlerComplete(x1_ipc_dispatch_tid);
        }
        if (x1_guest_wait_log) {
            x1_guest_wait_profiler.RecordCandidateHandlerComplete(x1_guest_wait_tid);
        }
    };

    if (!is_initialized) {
'''
    text = replace_once(text, anchor, replacement, "Ioctl2 guest-post-wait boundaries")
    nvdrv.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text, '#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n',
        '#include "core/x1_nvdrv_ipc_dispatch_profiler.h"\n#include "core/x1_guest_post_wait_profiler.h"\n',
        "guest-post-wait include in rasterizer")

    anchor = '''    Core::X1NvdrvIpcDispatchProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(
        text, anchor,
        '''    Core::X1NvdrvIpcDispatchProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    Core::X1GuestPostWaitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
''',
        "guest-post-wait initialization")

    anchor = '''    Core::X1NvdrvIpcDispatchProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(
        text, anchor,
        '''    Core::X1NvdrvIpcDispatchProfiler::Get().FrameEnd();
    Core::X1GuestPostWaitProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
''',
        "guest-post-wait frame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        settings: ["x1_guest_post_wait_attribution_log"],
        ui_cpp: ["X1 Log: Guest Post Wait Attribution"],
        kthread: ["RecordThreadStateTransition", "x1_old_wait_reason", "x1_current_svc_id"],
        nvdrv: ["RecordCandidateHandlerEntry", "RecordCandidateHandlerComplete"],
        rasterizer: [
            "X1GuestPostWaitProfiler::Get().Initialize",
            "X1GuestPostWaitProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    print("Transplanted exact dc95 X1 guest post-wait attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
