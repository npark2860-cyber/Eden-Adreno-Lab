#!/usr/bin/env python3
# Add observation-only Stage D CPU/scheduler and corrected wait attribution for the dynamic waker.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_once_in_region(
    text: str, region_start: str, region_end: str, old: str, new: str, label: str
) -> str:
    start = text.find(region_start)
    if start < 0:
        raise RuntimeError(f"{label}: region start not found")
    end = text.find(region_end, start + len(region_start))
    if end < 0:
        raise RuntimeError(f"{label}: region end not found")
    region = text[start:end]
    count = region.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match in region, got {count}")
    region = region.replace(old, new, 1)
    return text[:start] + region + text[end:]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_d_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_stage_d_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_stage_d_profiler.h must be copied before this pass")

    profiler_text = profiler.read_text(encoding="utf-8")
    if '#include <limits>\n' not in profiler_text:
        profiler_text = replace_once(
            profiler_text,
            '#include <cstddef>\n',
            '#include <cstddef>\n#include <limits>\n',
            "Stage D profiler numeric_limits include",
        )
        profiler.write_text(profiler_text, encoding="utf-8")

    # Matching SignalToAddress: keep Stage C intact, add Stage D samples at the same observation point.
    svc = root / "src/core/hle/kernel/svc/svc_address_arbiter.cpp"
    text = svc.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/core_timing.h"\n',
        "core timing include for Stage D cpu clock sample",
    )
    text = replace_once(
        text,
        '#include "core/x1_waker_pre_signal_profiler.h"\n',
        '#include "core/x1_waker_pre_signal_profiler.h"\n'
        '#include "core/x1_waker_stage_d_profiler.h"\n',
        "Stage D profiler include in address-arbiter svc",
    )
    anchor = '''        Core::X1WakerPreSignalProfiler::Get().RecordMatchingSignal(
            x1_signal_tid, x1_signal_context.pc, x1_signal_context.lr);
'''
    replacement = '''        Core::X1WakerPreSignalProfiler::Get().RecordMatchingSignal(
            x1_signal_tid, x1_signal_context.pc, x1_signal_context.lr);
        const s64 x1_signal_cpu_time = x1_signal_thread.GetCpuTime();
        Core::X1WakerStageDProfiler::Get().RecordMatchingSignal(
            x1_signal_tid, x1_signal_context.pc, x1_signal_context.lr,
            x1_signal_cpu_time > 0 ? static_cast<u64>(x1_signal_cpu_time) : 0,
            system.CoreTiming().GetClockTicks(), x1_signal_thread.GetPriority(),
            x1_signal_thread.GetActiveCore(), x1_signal_thread.GetCurrentCore());
'''
    text = replace_once(text, anchor, replacement, "Stage D matching-signal cpu/callsite sample")
    svc.write_text(text, encoding="utf-8")

    # KThread transitions: Stage D independently classifies completed waits using exit reason first,
    # then entry reason as a fallback for sites which assign their debug reason before BeginWait.
    kthread = root / "src/core/hle/kernel/k_thread.cpp"
    text = kthread.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_pre_signal_profiler.h"\n',
        '#include "core/x1_waker_pre_signal_profiler.h"\n'
        '#include "core/x1_waker_stage_d_profiler.h"\n',
        "Stage D profiler include in k_thread",
    )
    anchor = '''        if (x1_waker_log) {
            x1_waker_profiler.RecordThreadStateTransition(
                this->GetThreadId(), static_cast<u32>(x1_old_base_state),
                static_cast<u32>(state & ThreadState::Mask), static_cast<u32>(x1_old_wait_reason),
                x1_current_svc_id);
        }
'''
    replacement = anchor + '''        Core::X1WakerStageDProfiler::Get().RecordThreadStateTransition(
            this->GetThreadId(), static_cast<u32>(x1_old_base_state),
            static_cast<u32>(state & ThreadState::Mask), static_cast<u32>(x1_old_wait_reason));
'''
    text = replace_once(text, anchor, replacement, "Stage D KThread transition observation")

    wait_anchor = '''                    m_pinned_waiter_list.push_back(GetCurrentThread(kernel));
                    GetCurrentThread(kernel).BeginWait(kernel, std::addressof(wait_queue));
'''
    wait_replacement = '''                    m_pinned_waiter_list.push_back(GetCurrentThread(kernel));
                    Core::X1WakerStageDProfiler::Get().ArmNoneWaitSite(
                        GetCurrentThread(kernel).GetThreadId(),
                        Core::X1WakerStageDProfiler::NoneWaitSite::ThreadSetActivityPinned);
                    GetCurrentThread(kernel).BeginWait(kernel, std::addressof(wait_queue));
'''
    text = replace_once_in_region(
        text,
        "Result KThread::SetActivity",
        "Result KThread::GetThreadContext3",
        wait_anchor,
        wait_replacement,
        "SetActivity pinned direct BeginWait site",
    )

    wait_anchor = '''                        m_pinned_waiter_list.push_back(GetCurrentThread(kernel));
                        GetCurrentThread(kernel).BeginWait(kernel, std::addressof(wait_queue));
'''
    wait_replacement = '''                        m_pinned_waiter_list.push_back(GetCurrentThread(kernel));
                        Core::X1WakerStageDProfiler::Get().ArmNoneWaitSite(
                            GetCurrentThread(kernel).GetThreadId(),
                            Core::X1WakerStageDProfiler::NoneWaitSite::ThreadSetCoreMaskPinned);
                        GetCurrentThread(kernel).BeginWait(kernel, std::addressof(wait_queue));
'''
    text = replace_once_in_region(
        text,
        "Result KThread::SetCoreMask",
        "void KThread::SetBasePriority",
        wait_anchor,
        wait_replacement,
        "SetCoreMask pinned direct BeginWait site",
    )
    kthread.write_text(text, encoding="utf-8")

    # The exact dc95 user-exception claim path also enters Waiting without assigning a debug reason.
    # This comment+call pair is unique in exact dc95, so use a strict global one-shot replacement
    # instead of assuming the name of the next function.
    kprocess = root / "src/core/hle/kernel/k_process.cpp"
    text = kprocess.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_waker_stage_d_profiler.h"\n',
        "Stage D profiler include in k_process",
    )
    anchor = '''        // Wait to claim the exception thread.
        cur_thread->BeginWait(kernel, std::addressof(wait_queue));
'''
    replacement = '''        // Wait to claim the exception thread.
        Core::X1WakerStageDProfiler::Get().ArmNoneWaitSite(
            cur_thread->GetThreadId(),
            Core::X1WakerStageDProfiler::NoneWaitSite::ProcessUserException);
        cur_thread->BeginWait(kernel, std::addressof(wait_queue));
'''
    text = replace_once(text, anchor, replacement, "KProcess user-exception direct BeginWait site")
    kprocess.write_text(text, encoding="utf-8")

    # Reuse the existing Address Arbiter logging switch and frame report cadence.
    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_pre_signal_profiler.h"\n',
        '#include "core/x1_waker_pre_signal_profiler.h"\n'
        '#include "core/x1_waker_stage_d_profiler.h"\n',
        "Stage D profiler include in rasterizer",
    )
    anchor = '''    Core::X1WakerPreSignalProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    replacement = anchor + '''    Core::X1WakerStageDProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(text, anchor, replacement, "Stage D profiler initialization")
    anchor = '''    Core::X1WakerPreSignalProfiler::Get().FrameEnd();
'''
    replacement = anchor + '''    Core::X1WakerStageDProfiler::Get().FrameEnd();
'''
    text = replace_once(text, anchor, replacement, "Stage D profiler frame report")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKERD]",
            "RecordMatchingSignal",
            "RecordThreadStateTransition",
            "ThreadSetActivityPinned",
            "ThreadSetCoreMaskPinned",
            "ProcessUserException",
            "runUnschedAvg",
            "lr0=",
            "#include <limits>",
        ],
        svc: [
            "X1WakerStageDProfiler",
            "GetCpuTime()",
            "GetClockTicks()",
            "GetPriority()",
            "GetActiveCore()",
            "GetCurrentCore()",
        ],
        kthread: [
            "X1WakerStageDProfiler",
            "ThreadSetActivityPinned",
            "ThreadSetCoreMaskPinned",
        ],
        kprocess: ["X1WakerStageDProfiler", "ProcessUserException"],
        rasterizer: [
            "X1WakerStageDProfiler::Get().Initialize",
            "X1WakerStageDProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_profiler = profiler.read_text(encoding="utf-8")
    if "0x4f" in final_profiler.lower():
        raise RuntimeError("Stage D profiler must not hardcode the observed waker tid")
    if any(token in final_profiler for token in ("sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(")):
        raise RuntimeError("behavior-changing scheduling/wait token found in Stage D profiler")

    print("Transplanted exact dc95 X1 waker Stage D CPU/scheduler attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
