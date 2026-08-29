#!/usr/bin/env python3
# Add observation-only Stage J caller-of-caller attribution for Stage F selected producers.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_j_caller_depth.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_stage_j_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_stage_j_profiler.h must be copied before this pass")

    scheduler = root / "src/core/hle/kernel/k_scheduler.cpp"
    text = scheduler.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core_timing.h"\n',
        '#include "core/core_timing.h"\n#include "core/memory.h"\n',
        "Stage J memory include",
    )
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_g_profiler.h"\n',
        '#include "core/x1_waker_stage_g_profiler.h"\n#include "core/x1_waker_stage_j_profiler.h"\n',
        "Stage J profiler include",
    )

    g_call = '''        Core::X1WakerStageGProfiler::Get().RecordCpuSlice(
            static_cast<u32>(x1_stage_g_out_index), cur_thread->GetThreadId(),
            x1_stage_g_context.pc, x1_stage_g_context.lr, tick_diff,
            static_cast<u64>(cur_tick), cur_thread->GetPriority(), cur_thread->GetActiveCore(),
            cur_thread->GetCurrentCore());
'''
    j_call = g_call + '''
        u64 x1_stage_j_parent_lr = 0;
        auto x1_stage_j_parent_status =
            Core::X1WakerStageJProfiler::ParentStatus::Valid;
        const u64 x1_stage_j_fp = x1_stage_g_context.fp;
        if (x1_stage_j_fp == 0) {
            x1_stage_j_parent_status = Core::X1WakerStageJProfiler::ParentStatus::ZeroFp;
        } else if ((x1_stage_j_fp & (alignof(u64) - 1)) != 0 ||
                   x1_stage_j_fp > (~u64{0} - sizeof(u64))) {
            x1_stage_j_parent_status =
                Core::X1WakerStageJProfiler::ParentStatus::UnalignedOrOverflow;
        } else {
            const Common::ProcessAddress x1_stage_j_parent_slot{x1_stage_j_fp + sizeof(u64)};
            auto& x1_stage_j_memory = kernel.System().ApplicationMemory();
            if (!x1_stage_j_memory.IsValidVirtualAddressRange(x1_stage_j_parent_slot,
                                                               sizeof(u64))) {
                x1_stage_j_parent_status =
                    Core::X1WakerStageJProfiler::ParentStatus::InvalidRange;
            } else {
                x1_stage_j_parent_lr = x1_stage_j_memory.Read64(x1_stage_j_parent_slot);
                if (x1_stage_j_parent_lr == 0) {
                    x1_stage_j_parent_status =
                        Core::X1WakerStageJProfiler::ParentStatus::ZeroParent;
                }
            }
        }
        Core::X1WakerStageJProfiler::Get().RecordCpuSlice(
            static_cast<u32>(x1_stage_g_out_index), cur_thread->GetThreadId(),
            x1_stage_g_context.pc, x1_stage_g_context.lr, x1_stage_j_parent_lr,
            x1_stage_j_parent_status, tick_diff);
'''
    text = replace_once(text, g_call, j_call, "Stage J selected-producer parent LR sample")
    scheduler.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_g_profiler.h"\n',
        '#include "core/x1_waker_stage_g_profiler.h"\n#include "core/x1_waker_stage_j_profiler.h"\n',
        "Stage J rasterizer include",
    )
    g_init = '''    Core::X1WakerStageGProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(
        text,
        g_init,
        g_init + '''    Core::X1WakerStageJProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
''',
        "Stage J initialization",
    )
    frame_anchor = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    frame_replacement = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageJProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    text = replace_once(text, frame_anchor, frame_replacement, "Stage J frame report")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKERJ]", "ProducerCount = 2", "ContextSlotCount = 64", "ReportTopCount = 4",
            "ParentStatus", "parent_lr", "cpuTicks=", "top0=",
        ],
        scheduler: [
            "X1WakerStageJProfiler", "x1_stage_g_context.fp", "ApplicationMemory()",
            "IsValidVirtualAddressRange", "Read64", "x1_stage_j_parent_lr",
            "RecordCpuSlice",
        ],
        rasterizer: [
            "X1WakerStageJProfiler::Get().Initialize", "X1WakerStageJProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_scheduler = scheduler.read_text(encoding="utf-8")
    if final_scheduler.count("x1_stage_j_memory.Read64") != 1:
        raise RuntimeError("Stage J must perform exactly one selected-producer parent LR read site")
    if final_scheduler.count("x1_stage_g_context.fp") != 1:
        raise RuntimeError("Stage J must reuse exactly one saved selected-producer frame pointer")
    if "GetTrackedProducerIndex(cur_thread->GetThreadId())" not in final_scheduler:
        raise RuntimeError("Stage J is not guarded by Stage F selected-producer identity")

    raw_profiler = profiler.read_text(encoding="utf-8")
    raw_transplant = Path(__file__).read_text(encoding="utf-8")
    lowered = (raw_profiler + raw_transplant).lower()
    for forbidden_value in (
        "0x80", "0x81", "0x210b", "0x2181", "0x158528", "0x158420",
        "0x124a8c", "0x124b40", "0x127058", "0x13178c", "0x13f364",
    ):
        if forbidden_value in lowered:
            raise RuntimeError(f"Stage J must not hardcode runtime observation {forbidden_value}")

    behavior_tokens = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "YieldTo(", "QueueBuffer(", "swap_interval", "gpu_fence_behavior",
    )
    if any(token in raw_profiler for token in behavior_tokens):
        raise RuntimeError("behavior-changing token found in Stage J profiler")

    print("Transplanted exact dc95 X1 waker Stage J selected-producer caller depth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
