#!/usr/bin/env python3
# Add observation-only Stage G focused CPU-slice PC/LR attribution for Stage F producers.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_g_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_stage_g_profiler.h"
    stage_f = root / "src/core/x1_waker_stage_f_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_stage_g_profiler.h must be copied before this pass")
    if not stage_f.exists():
        raise RuntimeError("Stage F profiler must exist before Stage G pass")

    # Expose only the already-armed Stage F producer identity. Stage G does not rediscover TIDs.
    text = stage_f.read_text(encoding="utf-8")
    enabled_anchor = '''    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }
'''
    enabled_replacement = enabled_anchor + '''
    [[nodiscard]] s32 GetTrackedProducerIndex(u64 thread_id) const noexcept {
        if (!Enabled() || thread_id == 0) {
            return -1;
        }
        for (size_t i = 0; i < ProducerCount; ++i) {
            if (producers[i].thread_id.load(std::memory_order_acquire) == thread_id) {
                return static_cast<s32>(i);
            }
        }
        return -1;
    }
'''
    text = replace_once(text, enabled_anchor, enabled_replacement,
                        "Stage F tracked producer accessor")
    stage_f.write_text(text, encoding="utf-8")

    # Attribute exactly the tick_diff that exact dc95 adds to the switched-out KThread CPU total.
    # Read guest PC/LR only after the Stage F dynamic producer check succeeds.
    scheduler = root / "src/core/hle/kernel/k_scheduler.cpp"
    text = scheduler.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core_timing.h"\n',
        '#include "core/core_timing.h"\n'
        '#include "core/x1_waker_stage_f_profiler.h"\n'
        '#include "core/x1_waker_stage_g_profiler.h"\n',
        "Stage G profiler includes in kernel scheduler",
    )

    cpu_anchor = '''    const s64 tick_diff = cur_tick - prev_tick;
    cur_thread->AddCpuTime(m_core_id, tick_diff);
'''
    cpu_replacement = cpu_anchor + '''    const s32 x1_stage_g_out_index =
        Core::X1WakerStageFProfiler::Get().GetTrackedProducerIndex(cur_thread->GetThreadId());
    if (x1_stage_g_out_index >= 0) {
        const auto& x1_stage_g_context = cur_thread->GetContext();
        Core::X1WakerStageGProfiler::Get().RecordCpuSlice(
            static_cast<u32>(x1_stage_g_out_index), cur_thread->GetThreadId(),
            x1_stage_g_context.pc, x1_stage_g_context.lr, tick_diff,
            static_cast<u64>(cur_tick), cur_thread->GetPriority(), cur_thread->GetActiveCore(),
            cur_thread->GetCurrentCore());
    }
'''
    text = replace_once(text, cpu_anchor, cpu_replacement,
                        "Stage G selected producer switched-out CPU slice")

    switch_anchor = '''    // Set the new thread.
    SetCurrentThread(kernel, next_thread);
    m_current_thread = next_thread;
'''
    switch_replacement = '''    const s32 x1_stage_g_in_index =
        Core::X1WakerStageFProfiler::Get().GetTrackedProducerIndex(next_thread->GetThreadId());
    if (x1_stage_g_in_index >= 0) {
        Core::X1WakerStageGProfiler::Get().RecordScheduledIn(
            static_cast<u32>(x1_stage_g_in_index), next_thread->GetThreadId(),
            static_cast<u64>(cur_tick), next_thread->GetPriority(), next_thread->GetActiveCore(),
            next_thread->GetCurrentCore());
    }

    // Set the new thread.
    SetCurrentThread(kernel, next_thread);
    m_current_thread = next_thread;
'''
    text = replace_once(text, switch_anchor, switch_replacement,
                        "Stage G selected producer scheduled-in anchor")
    scheduler.write_text(text, encoding="utf-8")

    # Reuse the same Qualcomm/address-arbiter logging gate and report every 120 rendered frames.
    # Stage G reports before Stage F rotates discovery -> armed identities at the report boundary.
    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_f_profiler.h"\n',
        '#include "core/x1_waker_stage_f_profiler.h"\n'
        '#include "core/x1_waker_stage_g_profiler.h"\n',
        "Stage G profiler include in rasterizer",
    )
    init_anchor = '''    Core::X1WakerStageFProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    init_replacement = init_anchor + '''    Core::X1WakerStageGProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(text, init_anchor, init_replacement, "Stage G initialization")

    frame_anchor = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    frame_replacement = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    text = replace_once(text, frame_anchor, frame_replacement,
                        "Stage G frame report before Stage F identity rotation")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKERG]",
            "ProducerCount = 2",
            "ContextSlotCount = 64",
            "ReportTopCount = 4",
            "RecordScheduledIn",
            "RecordCpuSlice",
            "cpuTicks=",
            "top0=",
            "unknownTicks=",
            "overflowTicks=",
        ],
        stage_f: ["GetTrackedProducerIndex"],
        scheduler: [
            "X1WakerStageFProfiler",
            "X1WakerStageGProfiler",
            "GetTrackedProducerIndex(cur_thread->GetThreadId())",
            "GetTrackedProducerIndex(next_thread->GetThreadId())",
            "x1_stage_g_context.pc",
            "x1_stage_g_context.lr",
            "RecordCpuSlice",
            "RecordScheduledIn",
        ],
        rasterizer: [
            "X1WakerStageGProfiler::Get().Initialize",
            "X1WakerStageGProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    raw_profiler = profiler.read_text(encoding="utf-8")
    lowered = raw_profiler.lower()
    for forbidden_value in ("0x80", "0x81", "0x210"):
        if forbidden_value in lowered:
            raise RuntimeError(f"Stage G profiler must not hardcode runtime observation {forbidden_value}")

    forbidden = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "Yield", "QueueBuffer(", "swap_interval", "gpu_fence_behavior",
    )
    if any(token in raw_profiler for token in forbidden):
        raise RuntimeError("behavior-changing token found in Stage G profiler")

    final_scheduler = scheduler.read_text(encoding="utf-8")
    if final_scheduler.count("x1_stage_g_context = cur_thread->GetContext()") != 1:
        raise RuntimeError("Stage G must have exactly one selected-producer guest context sample")
    if final_scheduler.count("X1WakerStageGProfiler::Get().RecordCpuSlice") != 1:
        raise RuntimeError("Stage G must have exactly one switched-out CPU slice hook")
    if final_scheduler.count("X1WakerStageGProfiler::Get().RecordScheduledIn") != 1:
        raise RuntimeError("Stage G must have exactly one selected-producer scheduled-in hook")

    print("Transplanted exact dc95 X1 waker Stage G focused producer CPU attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
