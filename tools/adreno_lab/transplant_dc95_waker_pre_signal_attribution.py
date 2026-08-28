#!/usr/bin/env python3
# Add observation-only Stage C attribution for the dynamically identified AddressArbiter waker.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_pre_signal_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_pre_signal_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_pre_signal_profiler.h must be copied before this pass")

    svc = root / "src/core/hle/kernel/svc/svc_address_arbiter.cpp"
    text = svc.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_address_arbiter_profiler.h"\n',
        '#include "core/x1_address_arbiter_profiler.h"\n'
        '#include "core/x1_waker_pre_signal_profiler.h"\n',
        "waker profiler include in address-arbiter svc",
    )

    anchor = '''    if (x1_address_arbiter_profiler.ShouldTrackSignalAddress(address)) {
        const u64 x1_signal_tid = GetCurrentThread(system.Kernel()).GetThreadId();
        x1_address_arbiter_profiler.RecordSignal(
            x1_signal_tid, address, static_cast<u32>(signal_type), value, count);
    }

'''
    replacement = '''    if (x1_address_arbiter_profiler.ShouldTrackSignalAddress(address)) {
        auto& x1_signal_thread = GetCurrentThread(system.Kernel());
        const u64 x1_signal_tid = x1_signal_thread.GetThreadId();
        const auto& x1_signal_context = x1_signal_thread.GetContext();
        Core::X1WakerPreSignalProfiler::Get().RecordMatchingSignal(
            x1_signal_tid, x1_signal_context.pc, x1_signal_context.lr);
        x1_address_arbiter_profiler.RecordSignal(
            x1_signal_tid, address, static_cast<u32>(signal_type), value, count);
    }

'''
    text = replace_once(text, anchor, replacement, "matching-signal waker/callsite attribution")
    svc.write_text(text, encoding="utf-8")

    kthread = root / "src/core/hle/kernel/k_thread.cpp"
    text = kthread.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_guest_post_wait_profiler.h"\n',
        '#include "core/x1_guest_post_wait_profiler.h"\n'
        '#include "core/x1_waker_pre_signal_profiler.h"\n',
        "waker profiler include in k_thread",
    )

    anchor = '''    void KThread::SetState(KernelCore& kernel, ThreadState state) {
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
    replacement = '''    void KThread::SetState(KernelCore& kernel, ThreadState state) {
        KScopedSchedulerLock sl{kernel};
        auto& x1_guest_wait_profiler = Core::X1GuestPostWaitProfiler::Get();
        auto& x1_waker_profiler = Core::X1WakerPreSignalProfiler::Get();
        const bool x1_guest_wait_log = x1_guest_wait_profiler.Enabled();
        const bool x1_waker_log =
            x1_waker_profiler.Enabled() && x1_waker_profiler.ShouldTrackThread(this->GetThreadId());
        const bool x1_capture_wait_state = x1_guest_wait_log || x1_waker_log;
        const ThreadState x1_old_base_state =
            x1_capture_wait_state ? this->GetState() : ThreadState::Initialized;
        const auto x1_old_wait_reason = x1_capture_wait_state
                                            ? this->GetWaitReasonForDebugging()
                                            : ThreadWaitReasonForDebugging::None;
        const u8 x1_current_svc_id =
            x1_capture_wait_state ? this->GetStackParameters().current_svc_id : 0;

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
        if (x1_waker_log) {
            x1_waker_profiler.RecordThreadStateTransition(
                this->GetThreadId(), static_cast<u32>(x1_old_base_state),
                static_cast<u32>(state & ThreadState::Mask), static_cast<u32>(x1_old_wait_reason),
                x1_current_svc_id);
        }
        if (m_thread_state.load(std::memory_order_relaxed) != old_state) {
            KScheduler::OnThreadStateChanged(kernel, this, old_state);
        }
'''
    text = replace_once(text, anchor, replacement, "waker-only KThread wait-state attribution")
    kthread.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_address_arbiter_profiler.h"\n',
        '#include "core/x1_address_arbiter_profiler.h"\n'
        '#include "core/x1_waker_pre_signal_profiler.h"\n',
        "waker profiler include in rasterizer",
    )

    anchor = '''    Core::X1AddressArbiterProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    replacement = '''    Core::X1AddressArbiterProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    Core::X1WakerPreSignalProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(text, anchor, replacement, "waker profiler initialization")

    anchor = '''    Core::X1GuestPostWaitProfiler::Get().FrameEnd();
    Core::X1AddressArbiterProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    replacement = '''    Core::X1GuestPostWaitProfiler::Get().FrameEnd();
    Core::X1AddressArbiterProfiler::Get().FrameEnd();
    Core::X1WakerPreSignalProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(text, anchor, replacement, "waker profiler frame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKER]",
            "RecordMatchingSignal",
            "ShouldTrackThread",
            "RecordThreadStateTransition",
            "inter_signal_total_ns",
            "report_pc_mismatch",
            "report_lr_mismatch",
        ],
        svc: [
            "X1WakerPreSignalProfiler",
            "x1_signal_context.pc",
            "x1_signal_context.lr",
            "RecordMatchingSignal",
            "RecordSignal",
        ],
        kthread: [
            "X1WakerPreSignalProfiler",
            "x1_waker_log",
            "x1_capture_wait_state",
            "x1_waker_profiler.RecordThreadStateTransition",
        ],
        rasterizer: [
            "X1WakerPreSignalProfiler::Get().Initialize",
            "X1WakerPreSignalProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_profiler = profiler.read_text(encoding="utf-8")
    if "0x4f" in final_profiler.lower():
        raise RuntimeError("waker profiler must not hardcode the observed tid=0x4f")
    if any(token in final_profiler for token in ("sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(")):
        raise RuntimeError("behavior-changing scheduling/wait token found in waker profiler")

    print("Transplanted exact dc95 X1 dynamically latched waker pre-signal attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
