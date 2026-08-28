#!/usr/bin/env python3
"""Add observation-only X1 WaitForAddress and exact-address signal attribution."""

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

    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_guest_post_wait_attribution_log{
        linkage, false, "x1_guest_post_wait_attribution_log", Category::Debugging};
'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    Setting<bool> x1_address_arbiter_attribution_log{
        linkage, false, "x1_address_arbiter_attribution_log", Category::Debugging};
''',
        "address-arbiter setting",
    )
    settings.write_text(text, encoding="utf-8")

    ui_h = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_h.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};
    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};
    QCheckBox* x1_guest_post_wait_attribution_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(
        text,
        anchor,
        '''    QCheckBox* x1_guest_submit_thread_attribution_log_checkbox{};
    QCheckBox* x1_nvdrv_ipc_dispatch_gap_log_checkbox{};
    QCheckBox* x1_guest_post_wait_attribution_log_checkbox{};
    QCheckBox* x1_address_arbiter_attribution_log_checkbox{};

    const Core::System& system;
''',
        "address-arbiter widget member",
    )
    ui_h.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
    anchor = '''    x1_guest_post_wait_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Guest Post Wait Attribution"), this);

'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    x1_address_arbiter_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Address Arbiter Attribution"), this);

''',
        "address-arbiter widget construction",
    )

    anchor = '''    x1_guest_post_wait_attribution_log_checkbox->setToolTip(
        tr("Attribute the dominant submitter's post-NVDRV interval by KThread wait reason and SVC, "
           "and report the remaining runnable/CPU residual. Observation-only and disabled by default."));

'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    x1_address_arbiter_attribution_log_checkbox->setToolTip(
        tr("Aggregate WaitForAddress calls for the dynamic GPU submitter and exact-address "
           "SignalToAddress wake ownership. Requires Guest Post Wait Attribution."));

''',
        "address-arbiter tooltip",
    )

    anchor = '''    ui->gridLayout_1->addWidget(x1_guest_post_wait_attribution_log_checkbox, 11, 2, 1, 2);

'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    ui->gridLayout_1->addWidget(x1_address_arbiter_attribution_log_checkbox, 12, 0, 1, 2);

''',
        "address-arbiter layout",
    )

    anchor = '''    x1_guest_post_wait_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_guest_post_wait_attribution_log_checkbox->setChecked(
        Settings::values.x1_guest_post_wait_attribution_log.GetValue());
'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    x1_address_arbiter_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_address_arbiter_attribution_log_checkbox->setChecked(
        Settings::values.x1_address_arbiter_attribution_log.GetValue());
''',
        "address-arbiter widget state",
    )

    anchor = '''    Settings::values.x1_guest_post_wait_attribution_log =
        x1_guest_post_wait_attribution_log_checkbox->isChecked();
'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    Settings::values.x1_address_arbiter_attribution_log =
        x1_address_arbiter_attribution_log_checkbox->isChecked();
''',
        "address-arbiter widget apply",
    )

    anchor = '''    x1_guest_post_wait_attribution_log_checkbox->setText(
        tr("X1 Log: Guest Post Wait Attribution"));
}
'''
    text = replace_once(
        text,
        anchor,
        '''    x1_guest_post_wait_attribution_log_checkbox->setText(
        tr("X1 Log: Guest Post Wait Attribution"));
    x1_address_arbiter_attribution_log_checkbox->setText(
        tr("X1 Log: Address Arbiter Attribution"));
}
''',
        "address-arbiter widget retranslate",
    )
    ui_cpp.write_text(text, encoding="utf-8")

    text = guest_profiler.read_text(encoding="utf-8")
    anchor = '''    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

'''
    text = replace_once(
        text,
        anchor,
        anchor + '''    [[nodiscard]] bool IsTargetThreadWindowOpen(u64 thread_id) const noexcept {
        return Enabled() && thread_id != 0 &&
               thread_id == target_tid.load(std::memory_order_acquire) &&
               window_open.load(std::memory_order_acquire);
    }

''',
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

    anchor = '''    R_RETURN(
        GetCurrentProcess(system.Kernel()).WaitAddressArbiter(address, arb_type, value, timeout));
'''
    replacement = '''    auto& x1_guest_wait_profiler = Core::X1GuestPostWaitProfiler::Get();
    auto& x1_address_arbiter_profiler = Core::X1AddressArbiterProfiler::Get();
    const u64 x1_tid = GetCurrentThread(system.Kernel()).GetThreadId();
    const bool x1_track = x1_address_arbiter_profiler.Enabled() &&
                          x1_guest_wait_profiler.IsTargetThreadWindowOpen(x1_tid);
    const auto x1_token =
        x1_track ? x1_address_arbiter_profiler.BeginCall(
                       x1_tid, address, static_cast<u32>(arb_type), timeout_ns)
                 : Core::X1AddressArbiterProfiler::CallToken{};

    if (x1_token.active) {
        x1_address_arbiter_profiler.BeginTargetWait(x1_tid, address, x1_token.start_ns);
    }

    const Result result =
        GetCurrentProcess(system.Kernel()).WaitAddressArbiter(address, arb_type, value, timeout);

    if (x1_token.active) {
        x1_address_arbiter_profiler.EndCall(x1_token, R_SUCCEEDED(result), ResultTimedOut == result);
        x1_address_arbiter_profiler.EndTargetWait(x1_tid, address, x1_token.start_ns);
    }
    R_RETURN(result);
'''
    text = replace_once(text, anchor, replacement, "direct WaitForAddress attribution")

    anchor = '''    R_RETURN(GetCurrentProcess(system.Kernel())
                 .SignalAddressArbiter(address, signal_type, value, count));
'''
    replacement = '''    auto& x1_address_arbiter_profiler = Core::X1AddressArbiterProfiler::Get();
    if (x1_address_arbiter_profiler.ShouldTrackSignalAddress(address)) {
        const u64 x1_signal_tid = GetCurrentThread(system.Kernel()).GetThreadId();
        x1_address_arbiter_profiler.RecordSignal(
            x1_signal_tid, address, static_cast<u32>(signal_type), value, count);
    }

''' + anchor
    text = replace_once(text, anchor, replacement, "exact-address SignalToAddress attribution")
    svc.write_text(text, encoding="utf-8")

    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_guest_post_wait_profiler.h"\n',
        '#include "core/x1_guest_post_wait_profiler.h"\n#include "core/x1_address_arbiter_profiler.h"\n',
        "address-arbiter rasterizer include",
    )

    anchor = '''    Core::X1GuestPostWaitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
'''
    text = replace_once(
        text,
        anchor,
        '''    Core::X1GuestPostWaitProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    Core::X1AddressArbiterProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
''',
        "address-arbiter initialization",
    )

    anchor = '''    Core::X1GuestPostWaitProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(
        text,
        anchor,
        '''    Core::X1GuestPostWaitProfiler::Get().FrameEnd();
    Core::X1AddressArbiterProfiler::Get().FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
''',
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
        profiler: ["[X1-ADDRSIG]", "0x210adbc120ULL"],
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

    print("Transplanted exact dc95 X1 Address Arbiter wait + signal-owner attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
