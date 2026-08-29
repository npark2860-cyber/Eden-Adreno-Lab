#!/usr/bin/env python3
# Add observation-only Stage K one-more-frame attribution for Stage F selected producers.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_k_grandparent_depth.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_stage_k_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_stage_k_profiler.h must be copied before this pass")

    scheduler = root / "src/core/hle/kernel/k_scheduler.cpp"
    text = scheduler.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_j_profiler.h"\n',
        '#include "core/x1_waker_stage_j_profiler.h"\n#include "core/x1_waker_stage_k_profiler.h"\n',
        "Stage K profiler include",
    )

    j_call = '''        Core::X1WakerStageJProfiler::Get().RecordCpuSlice(
            static_cast<u32>(x1_stage_g_out_index), cur_thread->GetThreadId(),
            x1_stage_g_context.pc, x1_stage_g_context.lr, x1_stage_j_parent_lr,
            x1_stage_j_parent_status, tick_diff);
'''
    k_call = j_call + '''
        u64 x1_stage_k_grandparent_lr = 0;
        auto x1_stage_k_status = Core::X1WakerStageKProfiler::GrandparentStatus::Valid;
        if (x1_stage_j_parent_status != Core::X1WakerStageJProfiler::ParentStatus::Valid) {
            x1_stage_k_status =
                Core::X1WakerStageKProfiler::GrandparentStatus::ParentUnavailable;
        } else {
            auto& x1_stage_k_memory = x1_stage_j_memory;
            const Common::ProcessAddress x1_stage_k_parent_fp_slot{x1_stage_j_fp};
            if (!x1_stage_k_memory.IsValidVirtualAddressRange(x1_stage_k_parent_fp_slot,
                                                               sizeof(u64))) {
                x1_stage_k_status =
                    Core::X1WakerStageKProfiler::GrandparentStatus::InvalidParentFpRange;
            } else {
                const u64 x1_stage_k_parent_fp = x1_stage_k_memory.Read64(x1_stage_k_parent_fp_slot);
                if (x1_stage_k_parent_fp == 0) {
                    x1_stage_k_status =
                        Core::X1WakerStageKProfiler::GrandparentStatus::ZeroParentFp;
                } else if ((x1_stage_k_parent_fp & (alignof(u64) - 1)) != 0 ||
                           x1_stage_k_parent_fp <= x1_stage_j_fp ||
                           x1_stage_k_parent_fp > (~u64{0} - sizeof(u64))) {
                    x1_stage_k_status =
                        Core::X1WakerStageKProfiler::GrandparentStatus::BadParentFp;
                } else {
                    const Common::ProcessAddress x1_stage_k_grandparent_slot{
                        x1_stage_k_parent_fp + sizeof(u64)};
                    if (!x1_stage_k_memory.IsValidVirtualAddressRange(
                            x1_stage_k_grandparent_slot, sizeof(u64))) {
                        x1_stage_k_status = Core::X1WakerStageKProfiler::GrandparentStatus::
                            InvalidGrandparentRange;
                    } else {
                        x1_stage_k_grandparent_lr =
                            x1_stage_k_memory.Read64(x1_stage_k_grandparent_slot);
                        if (x1_stage_k_grandparent_lr == 0) {
                            x1_stage_k_status =
                                Core::X1WakerStageKProfiler::GrandparentStatus::ZeroGrandparent;
                        }
                    }
                }
            }
        }
        Core::X1WakerStageKProfiler::Get().RecordCpuSlice(
            static_cast<u32>(x1_stage_g_out_index), cur_thread->GetThreadId(),
            x1_stage_g_context.pc, x1_stage_g_context.lr, x1_stage_j_parent_lr,
            x1_stage_k_grandparent_lr, x1_stage_k_status, tick_diff);
'''
    text = replace_once(text, j_call, k_call, "Stage K selected-producer grandparent sample")
    scheduler.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_j_profiler.h"\n',
        '#include "core/x1_waker_stage_j_profiler.h"\n#include "core/x1_waker_stage_k_profiler.h"\n',
        "Stage K rasterizer include",
    )
    j_init = '''    Core::X1WakerStageJProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(
        text,
        j_init,
        j_init + '''    Core::X1WakerStageKProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
''',
        "Stage K initialization",
    )
    frame_anchor = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageJProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    frame_replacement = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageKProfiler::Get().FrameEnd();
    Core::X1WakerStageJProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    text = replace_once(text, frame_anchor, frame_replacement, "Stage K frame report")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKERK]", "ProducerCount = 2", "ContextSlotCount = 64", "ReportTopCount = 4",
            "GrandparentStatus", "grandparent_lr", "cpuTicks=", "top0=",
        ],
        scheduler: [
            "X1WakerStageKProfiler", "x1_stage_j_parent_status", "x1_stage_j_fp",
            "x1_stage_k_parent_fp", "x1_stage_k_grandparent_lr", "IsValidVirtualAddressRange",
            "x1_stage_k_memory.Read64", "RecordCpuSlice",
        ],
        rasterizer: [
            "X1WakerStageKProfiler::Get().Initialize", "X1WakerStageKProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_scheduler = scheduler.read_text(encoding="utf-8")
    if final_scheduler.count("x1_stage_k_memory.Read64") != 2:
        raise RuntimeError("Stage K must add exactly two selected-producer frame-record read sites")
    if final_scheduler.count("x1_stage_k_memory.IsValidVirtualAddressRange") != 2:
        raise RuntimeError("Stage K must range-validate both added read sites")
    if final_scheduler.count("x1_stage_g_context.fp") != 1:
        raise RuntimeError("Stage K must not add another direct saved-fp read")
    if "GetTrackedProducerIndex(cur_thread->GetThreadId())" not in final_scheduler:
        raise RuntimeError("Stage K is not guarded by Stage F selected-producer identity")
    if "x1_stage_k_parent_fp <= x1_stage_j_fp" not in final_scheduler:
        raise RuntimeError("Stage K must enforce monotonic frame-pointer ancestry")

    raw_profiler = profiler.read_text(encoding="utf-8")
    lowered = (raw_profiler + k_call).lower()
    for forbidden_value in (
        "0x80", "0x81", "0x210b", "0x2181", "0x158528", "0x158420",
        "0x124a8c", "0x124b40", "0x127058", "0x13178c", "0x127e54",
        "0x86a820", "0x86be08", "0x2a904cc",
    ):
        if forbidden_value in lowered:
            raise RuntimeError(f"Stage K must not hardcode runtime observation {forbidden_value}")

    behavior_tokens = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "YieldTo(", "QueueBuffer(", "swap_interval", "gpu_fence_behavior",
    )
    if any(token in raw_profiler for token in behavior_tokens):
        raise RuntimeError("behavior-changing token found in Stage K profiler")

    print("Transplanted exact dc95 X1 waker Stage K selected-producer grandparent depth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
