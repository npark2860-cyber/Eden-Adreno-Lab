#!/usr/bin/env python3
# Add observation-only Stage F CPU/wait attribution for the top two dynamic Stage E signal producers.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_f_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_stage_f_profiler.h"
    stage_e = root / "src/core/x1_waker_stage_e_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_stage_f_profiler.h must be copied before this pass")
    if not stage_e.exists():
        raise RuntimeError("Stage E profiler must exist before Stage F pass")

    svc = root / "src/core/hle/kernel/svc/svc_address_arbiter.cpp"
    text = svc.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_e_profiler.h"\n',
        '#include "core/x1_waker_stage_e_profiler.h"\n'
        '#include "core/x1_waker_stage_f_profiler.h"\n',
        "Stage F profiler include in address-arbiter svc",
    )

    signal_anchor = '''    auto& x1_stage_e_profiler = Core::X1WakerStageEProfiler::Get();
    if (x1_stage_e_profiler.ShouldTrackPromotedSignalAddress(address)) {
        const u64 x1_stage_e_signal_tid = GetCurrentThread(system.Kernel()).GetThreadId();
        x1_stage_e_profiler.RecordSignal(
            x1_stage_e_signal_tid, address, static_cast<u32>(signal_type), value, count);
    }
'''
    signal_replacement = '''    auto& x1_stage_e_profiler = Core::X1WakerStageEProfiler::Get();
    if (x1_stage_e_profiler.ShouldTrackPromotedSignalAddress(address)) {
        auto& x1_stage_f_signal_thread = GetCurrentThread(system.Kernel());
        const u64 x1_stage_e_signal_tid = x1_stage_f_signal_thread.GetThreadId();
        x1_stage_e_profiler.RecordSignal(
            x1_stage_e_signal_tid, address, static_cast<u32>(signal_type), value, count);
        const s64 x1_stage_f_cpu_time = x1_stage_f_signal_thread.GetCpuTime();
        Core::X1WakerStageFProfiler::Get().RecordPromotedSignal(
            x1_stage_e_signal_tid, address,
            x1_stage_f_cpu_time > 0 ? static_cast<u64>(x1_stage_f_cpu_time) : 0,
            system.CoreTiming().GetClockTicks(), x1_stage_f_signal_thread.GetPriority(),
            x1_stage_f_signal_thread.GetActiveCore(), x1_stage_f_signal_thread.GetCurrentCore());
    }
'''
    text = replace_once(text, signal_anchor, signal_replacement,
                        "Stage F promoted-key producer signal sample")
    svc.write_text(text, encoding="utf-8")

    kthread = root / "src/core/hle/kernel/k_thread.cpp"
    text = kthread.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_d_profiler.h"\n',
        '#include "core/x1_waker_stage_d_profiler.h"\n'
        '#include "core/x1_waker_stage_f_profiler.h"\n',
        "Stage F profiler include in k_thread",
    )
    transition_anchor = '''        Core::X1WakerStageDProfiler::Get().RecordThreadStateTransition(
            this->GetThreadId(), static_cast<u32>(x1_old_base_state),
            static_cast<u32>(state & ThreadState::Mask), static_cast<u32>(x1_old_wait_reason));
'''
    transition_replacement = transition_anchor + '''        Core::X1WakerStageFProfiler::Get().RecordThreadStateTransition(
            this->GetThreadId(), static_cast<u32>(x1_old_base_state),
            static_cast<u32>(state & ThreadState::Mask), static_cast<u32>(x1_old_wait_reason));
'''
    text = replace_once(text, transition_anchor, transition_replacement,
                        "Stage F producer KThread transition observation")
    kthread.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_e_profiler.h"\n',
        '#include "core/x1_waker_stage_e_profiler.h"\n'
        '#include "core/x1_waker_stage_f_profiler.h"\n',
        "Stage F profiler include in rasterizer",
    )
    init_anchor = '''    Core::X1WakerStageEProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    init_replacement = init_anchor + '''    Core::X1WakerStageFProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(text, init_anchor, init_replacement, "Stage F initialization")

    frame_anchor = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
'''
    frame_replacement = frame_anchor + '''    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    text = replace_once(text, frame_anchor, frame_replacement, "Stage F frame report")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKERF]",
            "ProducerCount = 2",
            "CandidateSlotCount = 16",
            "RecordPromotedSignal",
            "RecordThreadStateTransition",
            "SelectNextTracking",
            "runUnschedAvg",
        ],
        svc: [
            "X1WakerStageFProfiler",
            "x1_stage_f_signal_thread.GetCpuTime()",
            "system.CoreTiming().GetClockTicks()",
            "RecordPromotedSignal",
        ],
        kthread: [
            "X1WakerStageFProfiler",
            "X1WakerStageFProfiler::Get().RecordThreadStateTransition",
        ],
        rasterizer: [
            "X1WakerStageFProfiler::Get().Initialize",
            "X1WakerStageFProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_profiler = profiler.read_text(encoding="utf-8").lower()
    for forbidden_value in ("0x80", "0x81", "0x210"):
        if forbidden_value in final_profiler:
            raise RuntimeError(f"Stage F profiler must not hardcode runtime observation {forbidden_value}")

    forbidden = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "Yield", "QueueBuffer(", "swap_interval", "gpu_fence_behavior",
    )
    raw_profiler = profiler.read_text(encoding="utf-8")
    if any(token in raw_profiler for token in forbidden):
        raise RuntimeError("behavior-changing token found in Stage F profiler")

    print("Transplanted exact dc95 X1 waker Stage F producer CPU/wait attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
