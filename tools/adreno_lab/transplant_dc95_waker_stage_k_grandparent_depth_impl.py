#!/usr/bin/env python3
# Add observation-only Stage K grandparent + bounded x26 work-target identity attribution.

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
        auto& x1_stage_k_profiler = Core::X1WakerStageKProfiler::Get();
        auto& x1_stage_k_memory = kernel.System().ApplicationMemory();

        u64 x1_stage_k_grandparent_lr = 0;
        auto x1_stage_k_status = Core::X1WakerStageKProfiler::GrandparentStatus::Valid;
        if (x1_stage_j_parent_status != Core::X1WakerStageJProfiler::ParentStatus::Valid) {
            x1_stage_k_status =
                Core::X1WakerStageKProfiler::GrandparentStatus::ParentUnavailable;
        } else {
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

        u64 x1_stage_k_shim_offset = 0;
        u64 x1_stage_k_work_offset = 0;
        auto x1_stage_k_work_status = Core::X1WakerStageKProfiler::WorkTargetStatus::Valid;
        if (!x1_stage_k_profiler.HasMainModuleRange()) {
            x1_stage_k_work_status =
                Core::X1WakerStageKProfiler::WorkTargetStatus::MainRangeUnavailable;
        } else {
            const u64 x1_stage_k_node = x1_stage_g_context.r[26];
            if (x1_stage_k_node == 0) {
                x1_stage_k_work_status = Core::X1WakerStageKProfiler::WorkTargetStatus::ZeroNode;
            } else if ((x1_stage_k_node & (alignof(u64) - 1)) != 0) {
                x1_stage_k_work_status = Core::X1WakerStageKProfiler::WorkTargetStatus::BadNode;
            } else {
                const Common::ProcessAddress x1_stage_k_node_slot{x1_stage_k_node};
                if (!x1_stage_k_memory.IsValidVirtualAddressRange(x1_stage_k_node_slot,
                                                                   sizeof(u64))) {
                    x1_stage_k_work_status =
                        Core::X1WakerStageKProfiler::WorkTargetStatus::InvalidNodeRange;
                } else {
                    const u64 x1_stage_k_work_object =
                        x1_stage_k_memory.Read64(x1_stage_k_node_slot);
                    if (x1_stage_k_work_object == 0) {
                        x1_stage_k_work_status =
                            Core::X1WakerStageKProfiler::WorkTargetStatus::ZeroWorkObject;
                    } else if ((x1_stage_k_work_object & (alignof(u64) - 1)) != 0) {
                        x1_stage_k_work_status =
                            Core::X1WakerStageKProfiler::WorkTargetStatus::BadWorkObject;
                    } else {
                        const Common::ProcessAddress x1_stage_k_work_object_slot{
                            x1_stage_k_work_object};
                        if (!x1_stage_k_memory.IsValidVirtualAddressRange(
                                x1_stage_k_work_object_slot, sizeof(u64))) {
                            x1_stage_k_work_status = Core::X1WakerStageKProfiler::WorkTargetStatus::
                                InvalidWorkObjectRange;
                        } else {
                            const u64 x1_stage_k_vtable =
                                x1_stage_k_memory.Read64(x1_stage_k_work_object_slot);
                            if (x1_stage_k_vtable == 0) {
                                x1_stage_k_work_status =
                                    Core::X1WakerStageKProfiler::WorkTargetStatus::ZeroVtable;
                            } else if ((x1_stage_k_vtable & (alignof(u64) - 1)) != 0 ||
                                       x1_stage_k_vtable > (~u64{0} - 0x60)) {
                                x1_stage_k_work_status =
                                    Core::X1WakerStageKProfiler::WorkTargetStatus::BadVtable;
                            } else {
                                const Common::ProcessAddress x1_stage_k_shim_slot{
                                    x1_stage_k_vtable + 0x10};
                                if (!x1_stage_k_memory.IsValidVirtualAddressRange(
                                        x1_stage_k_shim_slot, sizeof(u64))) {
                                    x1_stage_k_work_status = Core::X1WakerStageKProfiler::
                                        WorkTargetStatus::InvalidShimRange;
                                } else {
                                    const u64 x1_stage_k_shim_target =
                                        x1_stage_k_memory.Read64(x1_stage_k_shim_slot);
                                    const Common::ProcessAddress x1_stage_k_work_target_slot{
                                        x1_stage_k_vtable + 0x60};
                                    if (!x1_stage_k_memory.IsValidVirtualAddressRange(
                                            x1_stage_k_work_target_slot, sizeof(u64))) {
                                        x1_stage_k_work_status = Core::X1WakerStageKProfiler::
                                            WorkTargetStatus::InvalidWorkTargetRange;
                                    } else {
                                        const u64 x1_stage_k_work_target =
                                            x1_stage_k_memory.Read64(x1_stage_k_work_target_slot);
                                        if (x1_stage_k_shim_target == 0 ||
                                            x1_stage_k_work_target == 0) {
                                            x1_stage_k_work_status = Core::X1WakerStageKProfiler::
                                                WorkTargetStatus::ZeroResolvedTarget;
                                        } else if (!x1_stage_k_profiler.NormalizeMainTarget(
                                                       x1_stage_k_shim_target,
                                                       x1_stage_k_shim_offset) ||
                                                   !x1_stage_k_profiler.NormalizeMainTarget(
                                                       x1_stage_k_work_target,
                                                       x1_stage_k_work_offset)) {
                                            x1_stage_k_shim_offset = 0;
                                            x1_stage_k_work_offset = 0;
                                            x1_stage_k_work_status = Core::X1WakerStageKProfiler::
                                                WorkTargetStatus::TargetOutsideMain;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        x1_stage_k_profiler.RecordCpuSlice(
            static_cast<u32>(x1_stage_g_out_index), cur_thread->GetThreadId(),
            x1_stage_g_context.pc, x1_stage_g_context.lr, x1_stage_j_parent_lr,
            x1_stage_k_grandparent_lr, x1_stage_k_status, x1_stage_k_shim_offset,
            x1_stage_k_work_offset, x1_stage_k_work_status, tick_diff);
'''
    text = replace_once(text, j_call, k_call, "Stage K selected-producer grandparent/work-target sample")
    scheduler.write_text(text, encoding="utf-8")

    loader = root / "src/core/loader/deconstructed_rom_directory.cpp"
    text = loader.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_waker_stage_k_profiler.h"\n',
        "Stage K loader profiler include",
    )
    h_anchor = '''        next_load_addr = *tentative_next_load_addr;
        modules.insert_or_assign(load_addr, module);
        LOG_DEBUG(Loader, "loaded module {} @ {:#x}", module, load_addr);
        if (Settings::values.x1_address_arbiter_attribution_log.GetValue()) {
            LOG_INFO(Loader,
                     "[X1-WAKERH] module={} base={:#x} end={:#x} size={:#x}",
                     module, load_addr, next_load_addr, next_load_addr - load_addr);
        }
'''
    h_replacement = h_anchor + '''        if (std::strcmp(module, "main") == 0) {
            Core::X1WakerStageKProfiler::Get().RegisterMainModuleRange(load_addr, next_load_addr);
        }
'''
    text = replace_once(text, h_anchor, h_replacement, "Stage K dynamic main-range registration")
    loader.write_text(text, encoding="utf-8")

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
            "[X1-WAKERK]", "ProducerCount = 2", "ContextSlotCount = 64",
            "WorkPairSlotCount = 64", "ReportTopCount = 4", "GrandparentStatus",
            "WorkTargetStatus", "RegisterMainModuleRange", "HasMainModuleRange",
            "NormalizeMainTarget", "workResolvedTicks=", "workOtherResolvedTicks=",
            "workTop0=",
        ],
        scheduler: [
            "X1WakerStageKProfiler", "x1_stage_j_parent_status", "x1_stage_j_fp",
            "x1_stage_k_parent_fp", "x1_stage_k_grandparent_lr", "x1_stage_g_context.r[26]",
            "x1_stage_k_node", "x1_stage_k_work_object", "x1_stage_k_vtable",
            "x1_stage_k_shim_target", "x1_stage_k_work_target", "NormalizeMainTarget",
            "IsValidVirtualAddressRange", "x1_stage_k_memory.Read64", "RecordCpuSlice",
        ],
        loader: [
            "[X1-WAKERH]", "X1WakerStageKProfiler", "RegisterMainModuleRange",
            'std::strcmp(module, "main") == 0',
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
    if final_scheduler.count("x1_stage_k_memory.Read64") != 6:
        raise RuntimeError("Stage K must contain exactly two frame reads plus four work-target reads")
    if final_scheduler.count("x1_stage_k_memory.IsValidVirtualAddressRange") != 6:
        raise RuntimeError("Stage K must range-validate all six Stage K memory reads")
    if final_scheduler.count("x1_stage_g_context.fp") != 1:
        raise RuntimeError("Stage K must not add another direct saved-fp read")
    if final_scheduler.count("x1_stage_g_context.r[26]") != 1:
        raise RuntimeError("Stage K work-target resolver must reuse saved x26 exactly once")
    if final_scheduler.count("x1_stage_g_context = cur_thread->GetContext()") != 1:
        raise RuntimeError("Stage K must not add another guest-context capture")
    if "GetTrackedProducerIndex(cur_thread->GetThreadId())" not in final_scheduler:
        raise RuntimeError("Stage K is not guarded by Stage F selected-producer identity")
    if "x1_stage_k_parent_fp <= x1_stage_j_fp" not in final_scheduler:
        raise RuntimeError("Stage K must enforce monotonic frame-pointer ancestry")

    final_loader = loader.read_text(encoding="utf-8")
    if final_loader.count("X1WakerStageKProfiler::Get().RegisterMainModuleRange") != 1:
        raise RuntimeError("Stage K must register the dynamic main module range exactly once")

    raw_profiler = profiler.read_text(encoding="utf-8")
    runtime_cpp = (raw_profiler + k_call + h_replacement).lower()
    for forbidden_value in (
        "0x85f12528", "0x85f12420", "0x85edea8c", "0x85edeb40",
        "0x158528", "0x158420", "0x124a8c", "0x124b40", "0x127058",
        "0x13178c", "0x127e54", "0x86a820", "0x86be08", "0x2a904cc",
        "0x86a490", "0x86bc9c", "0x2a2d958", "0x86a530", "0x86a678",
        "0x86a988", "0x2af1230", "0x26a7fc0", "0x2ae7b14", "0x249d114",
        "0x2afafb8", "0xc9f1e4", "0x2af178c", "0x2b01094", "0xd1d3f8",
        "0xc0eaa4", "0xa85380", "0x12c1304", "0x2460bcc", "0x9370e8",
        "0x2adc5f4", "0x2adbb54", "0x2af2ba0", "0x2488cf8", "0x2488e04",
        "0x2488fc0", "0x869624", "0xc1c28c", "0x9bc044", "0xd51f6c",
        "0xbd1b68", "0x12b6d4c", "0x2af1554", "0x2afc46c", "0xee96cc",
        "0x9143f4", "0x1219f54", "0x1015ffc", "0x2af1648", "0x77fa74",
        "0xf6a020", "0x2af3cbc", "0xad231c",
    ):
        if forbidden_value in runtime_cpp:
            raise RuntimeError(f"Stage K runtime C++ must not hardcode observation {forbidden_value}")

    behavior_tokens = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "YieldTo(", "QueueBuffer(", "swap_interval", "gpu_fence_behavior",
    )
    if any(token in raw_profiler + k_call + h_replacement for token in behavior_tokens):
        raise RuntimeError("behavior-changing token found in Stage K instrumentation")

    print("Transplanted exact dc95 X1 waker Stage K grandparent + x26 work-target identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
