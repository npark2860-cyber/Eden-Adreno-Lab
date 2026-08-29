#!/usr/bin/env python3
# Add observation-only Stage E recursive AddressArbiter attribution for the dynamic Stage D waker.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_waker_stage_e_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_waker_stage_e_profiler.h"
    stage_d = root / "src/core/x1_waker_stage_d_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_waker_stage_e_profiler.h must be copied before this pass")
    if not stage_d.exists():
        raise RuntimeError("Stage D profiler must exist before Stage E pass")

    svc = root / "src/core/hle/kernel/svc/svc_address_arbiter.cpp"
    text = svc.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_d_profiler.h"\n',
        '#include "core/x1_waker_stage_d_profiler.h"\n'
        '#include "core/x1_waker_stage_e_profiler.h"\n',
        "Stage E profiler include in address-arbiter svc",
    )

    wait_call = '''    const Result result =
        GetCurrentProcess(system.Kernel()).WaitAddressArbiter(address, arb_type, value, timeout);
'''
    wait_replacement = '''    const auto x1_stage_e_token = Core::X1WakerStageEProfiler::Get().BeginWait(
        x1_tid, address, static_cast<u32>(arb_type), value, timeout_ns);

    const Result result =
        GetCurrentProcess(system.Kernel()).WaitAddressArbiter(address, arb_type, value, timeout);
'''
    text = replace_once(text, wait_call, wait_replacement, "Stage E dynamic-waker WaitForAddress begin")

    wait_end = '''    if (x1_token.active) {
        x1_address_arbiter_profiler.EndCall(x1_token, R_SUCCEEDED(result), ResultTimedOut == result);
        x1_address_arbiter_profiler.EndTargetWait(x1_tid, address, x1_token.start_ns);
    }
    R_RETURN(result);
'''
    wait_end_replacement = '''    if (x1_token.active) {
        x1_address_arbiter_profiler.EndCall(x1_token, R_SUCCEEDED(result), ResultTimedOut == result);
        x1_address_arbiter_profiler.EndTargetWait(x1_tid, address, x1_token.start_ns);
    }
    if (x1_stage_e_token.active) {
        Core::X1WakerStageEProfiler::Get().EndWait(
            x1_stage_e_token, R_SUCCEEDED(result), ResultTimedOut == result);
    }
    R_RETURN(result);
'''
    text = replace_once(text, wait_end, wait_end_replacement, "Stage E dynamic-waker WaitForAddress end")

    signal_anchor = '''    R_RETURN(GetCurrentProcess(system.Kernel())
                 .SignalAddressArbiter(address, signal_type, value, count));
'''
    signal_replacement = '''    auto& x1_stage_e_profiler = Core::X1WakerStageEProfiler::Get();
    if (x1_stage_e_profiler.ShouldTrackPromotedSignalAddress(address)) {
        const u64 x1_stage_e_signal_tid = GetCurrentThread(system.Kernel()).GetThreadId();
        x1_stage_e_profiler.RecordSignal(
            x1_stage_e_signal_tid, address, static_cast<u32>(signal_type), value, count);
    }

''' + signal_anchor
    text = replace_once(text, signal_anchor, signal_replacement,
                        "Stage E promoted-key SignalToAddress attribution")
    svc.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_d_profiler.h"\n',
        '#include "core/x1_waker_stage_d_profiler.h"\n'
        '#include "core/x1_waker_stage_e_profiler.h"\n',
        "Stage E profiler include in rasterizer",
    )

    init_anchor = '''    Core::X1WakerStageDProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    init_replacement = init_anchor + '''    Core::X1WakerStageEProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(text, init_anchor, init_replacement, "Stage E initialization")

    frame_anchor = '''    Core::X1WakerStageDProfiler::Get().FrameEnd();
'''
    frame_replacement = frame_anchor + '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
'''
    text = replace_once(text, frame_anchor, frame_replacement, "Stage E frame report")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-WAKERE]",
            "X1WakerStageDProfiler::Get().ShouldTrackThread",
            "FindOrClaimWaitSlot",
            "ShouldTrackPromotedSignalAddress",
            "FindOrClaimSignalSlot",
            "nextPromoted",
            "w2s",
            "s2e",
        ],
        svc: [
            "X1WakerStageEProfiler",
            "x1_stage_e_token",
            "BeginWait",
            "EndWait",
            "ShouldTrackPromotedSignalAddress",
            "RecordSignal",
        ],
        rasterizer: [
            "X1WakerStageEProfiler::Get().Initialize",
            "X1WakerStageEProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_profiler = profiler.read_text(encoding="utf-8")
    if "0x4f" in final_profiler.lower():
        raise RuntimeError("Stage E profiler must not hardcode observed waker tid")
    if "0x210" in final_profiler.lower():
        raise RuntimeError("Stage E profiler must not hardcode a process-specific guest wait address")
    forbidden = (
        "sleep_for", "sleep_until", "SetPriority(", "SetCoreMask(", "Reschedule(",
        "Yield", "QueueBuffer(", "swap_interval", "gpu_fence_behavior",
    )
    if any(token in final_profiler for token in forbidden):
        raise RuntimeError("behavior-changing token found in Stage E profiler")

    print("Transplanted exact dc95 X1 waker Stage E recursive AddressArbiter attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
