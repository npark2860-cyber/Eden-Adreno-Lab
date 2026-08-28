#!/usr/bin/env python3
"""Add observation-only X1 WaitForAddress and dynamically latched signal attribution."""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_address_arbiter_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_address_arbiter_profiler.h"
    guest_profiler = root / "src/core/x1_guest_post_wait_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_address_arbiter_profiler.h must be copied before this pass")
    if not guest_profiler.exists():
        raise RuntimeError("guest-post-wait profiler must exist before Address Arbiter pass")

    # Stage B v1 used the absolute guest VA observed in one run. The same logical wait object
    # relocated by +8 MiB in the next run, so convert the copied profiler template to latch the
    # first post-warmup target-thread WaitIfEqual(timeout=-1) address for the current process.
    profiler_text = profiler.read_text(encoding="utf-8")
    profiler_text = replace_once(
        profiler_text,
        '''        signal_slot_overflow.store(0, std::memory_order_relaxed);\n        target_wait_start_ns.store(0, std::memory_order_relaxed);\n''',
        '''        signal_slot_overflow.store(0, std::memory_order_relaxed);\n        target_signal_address.store(0, std::memory_order_relaxed);\n        target_wait_start_ns.store(0, std::memory_order_relaxed);\n''',
        "dynamic signal target initialize",
    )
    profiler_text = replace_once(
        profiler_text,
        '''    [[nodiscard]] bool ShouldTrackSignalAddress(u64 address) const noexcept {\n        return Enabled() && armed.load(std::memory_order_acquire) && address == TargetSignalAddress;\n    }\n''',
        '''    [[nodiscard]] bool ShouldTrackSignalAddress(u64 address) const noexcept {\n        const u64 target = target_signal_address.load(std::memory_order_acquire);\n        return Enabled() && armed.load(std::memory_order_acquire) && target != 0 &&\n               address == target;\n    }\n''',
        "dynamic signal target predicate",
    )
    profiler_text = replace_once(
        profiler_text,
        '''        target_tid.store(thread_id, std::memory_order_release);\n\n        const u32 slot_index = FindOrClaimSlot(address, arbitration_type, timeout_ns);\n''',
        '''        target_tid.store(thread_id, std::memory_order_release);\n\n        if (arbitration_type == 2 && timeout_ns == -1 && address != 0) {\n            u64 expected = 0;\n            target_signal_address.compare_exchange_strong(expected, address,\n                                                          std::memory_order_acq_rel,\n                                                          std::memory_order_relaxed);\n        }\n\n        const u32 slot_index = FindOrClaimSlot(address, arbitration_type, timeout_ns);\n''',
        "dynamic signal target latch",
    )
    profiler_text = replace_once(
        profiler_text,
        '''    static constexpr u32 SignalSlotCount = 8;\n    static constexpr u64 TargetSignalAddress = 0x210adbc120ULL;\n''',
        '''    static constexpr u32 SignalSlotCount = 8;\n''',
        "remove fixed signal target",
    )
    profiler_text = replace_once(
        profiler_text,
        '''                 frame, frames, TargetSignalAddress,\n                 target_wait_tid.load(std::memory_order_relaxed), active_slots, total_calls,\n''',
        '''                 frame, frames, target_signal_address.load(std::memory_order_relaxed),\n                 target_wait_tid.load(std::memory_order_relaxed), active_slots, total_calls,\n''',
        "dynamic signal target report",
    )
    profiler_text = replace_once(
        profiler_text,
        '''    std::atomic<u64> signal_slot_overflow{0};\n    std::atomic<u64> target_wait_start_ns{0};\n''',
        '''    std::atomic<u64> signal_slot_overflow{0};\n    std::atomic<u64> target_signal_address{0};\n    std::atomic<u64> target_wait_start_ns{0};\n''',
        "dynamic signal target storage",
    )
    profiler.write_text(profiler_text, encoding="utf-8")

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_guest_post_wait_attribution_log{\n        linkage, false, "x1_guest_post_wait_attribution_log", Category::Debugging};\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    Setting<bool> x1_address_arbiter_attribution_log{\n        linkage, false, "x1_address_arbiter_attribution_log", Category::Debugging};\n''',
        "address-arbiter setting",
    )
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};\n    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};\n    QCheckBox* x1_guest_post_wait_attribution_log_checkbox{};\n\n    const Core::System& system;\n'''
    text = replace_once(
        text,
        anchor,
        '''    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};\n    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};\n    QCheckBox* x1_guest_post_wait_attribution_log_checkbox{};\n    QCheckBox* x1_address_arbiter_attribution_log_checkbox{};\n\n    const Core::System& system;\n''',
        "address-arbiter widget member",
    )
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
    anchor = '''    x1_guest_post_wait_attribution_log_checkbox =\n        new QCheckBox(tr("X1 Log: Guest Post Wait Attribution"), this);\n\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    x1_address_arbiter_attribution_log_checkbox =\n        new QCheckBox(tr("X1 Log: Address Arbiter Attribution"), this);\n\n''',
        "address-arbiter widget construction",
    )

    anchor = '''    x1_guest_post_wait_attribution_log_checkbox->setToolTip(\n        tr("Attribute the dominant submitter's post-NVDRV interval by KThread wait reason and SVC, "\n           "and report the remaining runnable/CPU residual. Observation-only and disabled by default."));\n\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    x1_address_arbiter_attribution_log_checkbox->setToolTip(\n        tr("Aggregate WaitForAddress calls for the dynamic GPU submitter and dynamically latched "\n           "SignalToAddress wake ownership. Requires Guest Post Wait Attribution."));\n\n''',
        "address-arbiter tooltip",
    )

    anchor = '''    ui->gridLayout_1->addWidget(x1_guest_post_wait_attribution_log_checkbox, 11, 2, 1, 2);\n\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    ui->gridLayout_1->addWidget(x1_address_arbiter_attribution_log_checkbox, 12, 0, 1, 2);\n\n''',
        "address-arbiter layout",
    )

    anchor = '''    x1_guest_post_wait_attribution_log_checkbox->setEnabled(runtime_lock);\n    x1_guest_post_wait_attribution_log_checkbox->setChecked(\n        Settings::values.x1_guest_post_wait_attribution_log.GetValue());\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    x1_address_arbiter_attribution_log_checkbox->setEnabled(runtime_lock);\n    x1_address_arbiter_attribution_log_checkbox->setChecked(\n        Settings::values.x1_address_arbiter_attribution_log.GetValue());\n''',
        "address-arbiter widget state",
    )

    anchor = '''    Settings::values.x1_guest_post_wait_attribution_log =\n        x1_guest_post_wait_attribution_log_checkbox->isChecked();\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    Settings::values.x1_address_arbiter_attribution_log =\n        x1_address_arbiter_attribution_log_checkbox->isChecked();\n''',
        "address-arbiter widget apply",
    )

    anchor = '''    x1_guest_post_wait_attribution_log_checkbox->setText(\n        tr("X1 Log: Guest Post Wait Attribution"));\n}\n'''
    text = replace_once(
        text,
        anchor,
        '''    x1_guest_post_wait_attribution_log_checkbox->setText(\n        tr("X1 Log: Guest Post Wait Attribution"));\n    x1_address_arbiter_attribution_log_checkbox->setText(\n        tr("X1 Log: Address Arbiter Attribution"));\n}\n''',
        "address-arbiter widget retranslate",
    )
    ui_cpp.write_text(text, encoding="utf-8")

    text = guest_profiler.read_text(encoding="utf-8")
    anchor = '''    [[nodiscard]] bool Enabled() const noexcept {\n        return enabled.load(std::memory_order_relaxed);\n    }\n\n'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    [[nodiscard]] bool IsTargetThreadWindowOpen(u64 thread_id) const noexcept {\n        return Enabled() && thread_id != 0 &&\n               thread_id == target_tid.load(std::memory_order_acquire) &&\n               window_open.load(std::memory_order_acquire);\n    }\n\n''',
        "guest-post-wait target/window accessor",
    )
    guest_profiler.write_text(text, encoding="utf-8")

    svc = root / "src/core/hle/kernel/svc/svc_address_arbiter.cpp"
    text = svc.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/core.h"\n',
        '#include "core/core.h"\n#include "core/x1_address_arbiter_profiler.h"\n#include "core/x1_guest_post_wait_profiler.h"\n',
        "address-arbiter profiler includes",
    )
    text = replace_once(
        text,
        '#include "core/hle/kernel/k_process.h"\n',
        '#include "core/hle/kernel/k_process.h"\n#include "core/hle/kernel/k_thread.h"\n',
        "address-arbiter KThread include",
    )

    anchor = '''    R_RETURN(\n        GetCurrentProcess(system.Kernel()).WaitAddressArbiter(address, arb_type, value, timeout));\n'''
    replacement = '''    auto& x1_guest_wait_profiler = Core::X1GuestPostWaitProfiler::Get();\n    auto& x1_address_arbiter_profiler = Core::X1AddressArbiterProfiler::Get();\n    const u64 x1_tid = GetCurrentThread(system.Kernel()).GetThreadId();\n    const bool x1_track = x1_address_arbiter_profiler.Enabled() &&\n                          x1_guest_wait_profiler.IsTargetThreadWindowOpen(x1_tid);\n    const auto x1_token =\n        x1_track ? x1_address_arbiter_profiler.BeginCall(\n                       x1_tid, address, static_cast<u32>(arb_type), timeout_ns)\n                 : Core::X1AddressArbiterProfiler::CallToken{};\n\n    if (x1_token.active) {\n        x1_address_arbiter_profiler.BeginTargetWait(x1_tid, address, x1_token.start_ns);\n    }\n\n    const Result result =\n        GetCurrentProcess(system.Kernel()).WaitAddressArbiter(address, arb_type, value, timeout);\n\n    if (x1_token.active) {\n        x1_address_arbiter_profiler.EndCall(x1_token, R_SUCCEEDED(result), ResultTimedOut == result);\n        x1_address_arbiter_profiler.EndTargetWait(x1_tid, address, x1_token.start_ns);\n    }\n    R_RETURN(result);\n'''
    text = replace_once(text, anchor, replacement, "direct WaitForAddress attribution")

    anchor = '''    R_RETURN(GetCurrentProcess(system.Kernel())\n                 .SignalAddressArbiter(address, signal_type, value, count));\n'''
    replacement = '''    auto& x1_address_arbiter_profiler = Core::X1AddressArbiterProfiler::Get();\n    if (x1_address_arbiter_profiler.ShouldTrackSignalAddress(address)) {\n        const u64 x1_signal_tid = GetCurrentThread(system.Kernel()).GetThreadId();\n        x1_address_arbiter_profiler.RecordSignal(\n            x1_signal_tid, address, static_cast<u32>(signal_type), value, count);\n    }\n\n''' + anchor
    text = replace_once(text, anchor, replacement, "dynamic-address SignalToAddress attribution")
    svc.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_guest_post_wait_profiler.h"\n',
        '#include "core/x1_guest_post_wait_profiler.h"\n#include "core/x1_address_arbiter_profiler.h"\n',
        "address-arbiter rasterizer include",
    )

    anchor = '''    Core::X1GuestPostWaitProfiler::Get().Initialize(\n        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);\n}\n'''
    text = replace_once(
        text,
        anchor,
        '''    Core::X1GuestPostWaitProfiler::Get().Initialize(\n        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);\n    Core::X1AddressArbiterProfiler::Get().Initialize(\n        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);\n}\n''',
        "address-arbiter initialization",
    )

    anchor = '''    Core::X1GuestPostWaitProfiler::Get().FrameEnd();\n}\n\nbool RasterizerVulkan::AccelerateConditionalRendering() {\n'''
    text = replace_once(
        text,
        anchor,
        '''    Core::X1GuestPostWaitProfiler::Get().FrameEnd();\n    Core::X1AddressArbiterProfiler::Get().FrameEnd();\n}\n\nbool RasterizerVulkan::AccelerateConditionalRendering() {\n''',
        "address-arbiter frame report hook",
    )
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        settings: ["x1_address_arbiter_attribution_log"],
        ui_cpp: ["X1 Log: Address Arbiter Attribution"],
        guest_profiler: ["IsTargetThreadWindowOpen"],
        svc: [
            "X1AddressArbiterProfiler",
            "BeginCall",
            "EndCall",
            "BeginTargetWait",
            "EndTargetWait",
            "ShouldTrackSignalAddress",
            "RecordSignal",
        ],
        profiler: [
            "[X1-ADDRSIG]",
            "target_signal_address",
            "arbitration_type == 2 && timeout_ns == -1",
        ],
        rasterizer: [
            "X1AddressArbiterProfiler::Get().Initialize",
            "X1AddressArbiterProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_profiler = profiler.read_text(encoding="utf-8")
    if "0x210adbc120ULL" in final_profiler:
        raise RuntimeError("fixed Stage B v1 signal target leaked into generated profiler")

    print("Transplanted exact dc95 X1 Address Arbiter wait + dynamic signal-owner attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
