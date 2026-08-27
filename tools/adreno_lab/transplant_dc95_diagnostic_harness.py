#!/usr/bin/env python3
'''Add runtime-selectable X1 diagnostic harness controls on top of the exact-dc95 chain.

Expected order:
  - recreate existing X1 diagnostic chain through Uniform cache A/B
  - transplant_dc95_frame_cadence_attribution.py
  - transplant_dc95_swap_interval_3_to_2_ab.py
  - this pass

This pass does not add a new rendering/timing policy. It:
  1. separates frame-cadence logging from the older x1_present_frame_log switch,
  2. adds observation-only DequeueBuffer timing,
  3. keeps all previously prepared A/B controls in the same binary.

Dequeue attribution splits the producer cycle into:
  previous QueueBuffer -> DequeueBuffer entry
  DequeueBuffer entry -> free-slot selection/return
  DequeueBuffer return -> next QueueBuffer

No wait, fence, buffer-count, swap-interval, VI, scheduler, present, barrier, render-pass,
Uniform, alias, or GPU policy is changed by this pass.
'''

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def extract_between(text: str, start: str, end: str, label: str) -> str:
    start_pos = text.find(start)
    if start_pos < 0:
        raise RuntimeError(f"{label}: start marker missing")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise RuntimeError(f"{label}: end marker missing")
    return text[start_pos:end_pos]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_diagnostic_harness.py <eden-root>")

    root = Path(sys.argv[1])

    settings = root / "src/common/settings.h"
    settings_text = settings.read_text(encoding="utf-8")
    for marker in (
        "x1_present_frame_log",
        "x1_descriptor_ring_log",
        "x1_ab_skip_draw",
        "x1_ab_skip_dispatch",
        "x1_ab_disable_adaptive_uniform_fast_stream",
        "x1_ab_clamp_main_swap_interval_3_to_2",
    ):
        if marker not in settings_text:
            raise RuntimeError(f"required parent setting missing: {marker}")

    settings_anchor = '''    Setting<bool> x1_ab_clamp_main_swap_interval_3_to_2{
        linkage, false, "x1_ab_clamp_main_swap_interval_3_to_2", Category::Debugging};
'''
    settings_replacement = settings_anchor + '''    Setting<bool> x1_frame_cadence_log{
        linkage, false, "x1_frame_cadence_log", Category::Debugging};
    Setting<bool> x1_dequeue_attribution_log{
        linkage, false, "x1_dequeue_attribution_log", Category::Debugging};
'''
    settings_text = replace_once(
        settings_text, settings_anchor, settings_replacement, "diagnostic harness settings"
    )
    settings.write_text(settings_text, encoding="utf-8")

    header = root / "src/yuzu/configuration/configure_debug.h"
    header_text = header.read_text(encoding="utf-8")
    member_anchor = '''    QCheckBox* x1_ab_clamp_main_swap_interval_3_to_2_checkbox{};

    const Core::System& system;
'''
    member_replacement = '''    QCheckBox* x1_ab_clamp_main_swap_interval_3_to_2_checkbox{};
    QCheckBox* x1_frame_cadence_log_checkbox{};
    QCheckBox* x1_dequeue_attribution_log_checkbox{};

    const Core::System& system;
'''
    header_text = replace_once(
        header_text, member_anchor, member_replacement, "diagnostic harness widget members"
    )
    header.write_text(header_text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    cpp_text = cpp.read_text(encoding="utf-8")

    construction_anchor = '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox =
        new QCheckBox(tr("X1 A/B: Clamp Main Swap Interval 3 To 2"), this);

'''
    construction_replacement = construction_anchor + '''    x1_frame_cadence_log_checkbox =
        new QCheckBox(tr("X1 Log: Frame Cadence"), this);
    x1_dequeue_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Dequeue Attribution"), this);

'''
    cpp_text = replace_once(
        cpp_text, construction_anchor, construction_replacement,
        "diagnostic harness widget construction"
    )

    tooltip_anchor = '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setToolTip(
        tr("EXPERIMENT: in the X1 Windows ARM64 Vulkan diagnostic build, preserve raw guest "
           "swap=3 but use effective main-layer acquire/release interval 2. Disabled by default."));

'''
    tooltip_replacement = tooltip_anchor + '''    x1_frame_cadence_log_checkbox->setToolTip(
        tr("Log QueueBuffer, main-layer acquire, and 60-Hz VI cadence records. Disabled by default."));
    x1_dequeue_attribution_log_checkbox->setToolTip(
        tr("Log DequeueBuffer entry, free-slot selection time, return time, and the QueueBuffer "
           "records needed to split producer-frame latency. Disabled by default."));

'''
    cpp_text = replace_once(
        cpp_text, tooltip_anchor, tooltip_replacement, "diagnostic harness tooltips"
    )

    layout_anchor = '''    ui->gridLayout_1->addWidget(x1_ab_clamp_main_swap_interval_3_to_2_checkbox,
                                7, 2, 1, 2);

'''
    layout_replacement = layout_anchor + '''    ui->gridLayout_1->addWidget(x1_frame_cadence_log_checkbox, 8, 0, 1, 2);
    ui->gridLayout_1->addWidget(x1_dequeue_attribution_log_checkbox, 8, 2, 1, 2);

'''
    cpp_text = replace_once(
        cpp_text, layout_anchor, layout_replacement, "diagnostic harness widget layout"
    )

    state_anchor = '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setEnabled(runtime_lock);
    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setChecked(
        Settings::values.x1_ab_clamp_main_swap_interval_3_to_2.GetValue());
'''
    state_replacement = state_anchor + '''    x1_frame_cadence_log_checkbox->setEnabled(runtime_lock);
    x1_frame_cadence_log_checkbox->setChecked(
        Settings::values.x1_frame_cadence_log.GetValue());
    x1_dequeue_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_dequeue_attribution_log_checkbox->setChecked(
        Settings::values.x1_dequeue_attribution_log.GetValue());
'''
    cpp_text = replace_once(
        cpp_text, state_anchor, state_replacement, "diagnostic harness widget state"
    )

    apply_anchor = '''    Settings::values.x1_ab_clamp_main_swap_interval_3_to_2 =
        x1_ab_clamp_main_swap_interval_3_to_2_checkbox->isChecked();
'''
    apply_replacement = apply_anchor + '''    Settings::values.x1_frame_cadence_log =
        x1_frame_cadence_log_checkbox->isChecked();
    Settings::values.x1_dequeue_attribution_log =
        x1_dequeue_attribution_log_checkbox->isChecked();
'''
    cpp_text = replace_once(
        cpp_text, apply_anchor, apply_replacement, "diagnostic harness widget apply"
    )

    retranslate_anchor = '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setText(
        tr("X1 A/B: Clamp Main Swap Interval 3 To 2"));
}
'''
    retranslate_replacement = '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setText(
        tr("X1 A/B: Clamp Main Swap Interval 3 To 2"));
    x1_frame_cadence_log_checkbox->setText(tr("X1 Log: Frame Cadence"));
    x1_dequeue_attribution_log_checkbox->setText(tr("X1 Log: Dequeue Attribution"));
}
'''
    cpp_text = replace_once(
        cpp_text, retranslate_anchor, retranslate_replacement,
        "diagnostic harness widget retranslate"
    )
    cpp.write_text(cpp_text, encoding="utf-8")

    producer = root / "src/core/hle/service/nvnflinger/buffer_queue_producer.cpp"
    producer_text = producer.read_text(encoding="utf-8")
    wait_helper_before = extract_between(
        producer_text,
        "Status BufferQueueProducer::WaitForFreeSlotThenRelock(",
        "Status BufferQueueProducer::DequeueBuffer(",
        "WaitForFreeSlotThenRelock helper",
    )

    queue_gate_anchor = '''    if (Settings::values.x1_present_frame_log.GetValue()) {
        const auto x1_queue_host_us = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        LOG_INFO(Service_Nvnflinger,
                 "[X1-CADENCE][QUEUE] hostUs={} core=0x{:x} frame={} slot={} swap={}",
                 x1_queue_host_us, reinterpret_cast<std::uintptr_t>(core.get()), item.frame_number,
                 slot, item.swap_interval);
    }
'''
    queue_gate_replacement = '''    if (Settings::values.x1_frame_cadence_log.GetValue() ||
        Settings::values.x1_dequeue_attribution_log.GetValue()) {
        const auto x1_queue_host_us = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        LOG_INFO(Service_Nvnflinger,
                 "[X1-CADENCE][QUEUE] hostUs={} core=0x{:x} frame={} slot={} swap={}",
                 x1_queue_host_us, reinterpret_cast<std::uintptr_t>(core.get()), item.frame_number,
                 slot, item.swap_interval);
    }
'''
    producer_text = replace_once(
        producer_text, queue_gate_anchor, queue_gate_replacement,
        "QueueBuffer harness log gate"
    )

    dequeue_prefix = '''Status BufferQueueProducer::DequeueBuffer(s32* out_slot, Fence* out_fence, bool async, u32 width,
                                          u32 height, PixelFormat format, u32 usage) {
    LOG_DEBUG(Service_Nvnflinger, "async={} w={} h={} format={}, usage={}",
              async ? "true" : "false", width, height, format, usage);

'''
    dequeue_prefix_replacement = dequeue_prefix + '''    const bool x1_dequeue_log =
        Settings::values.x1_dequeue_attribution_log.GetValue();
    const auto x1_dequeue_start =
        x1_dequeue_log ? std::chrono::steady_clock::now()
                       : std::chrono::steady_clock::time_point{};
    const auto x1_dequeue_call_us =
        x1_dequeue_log
            ? std::chrono::duration_cast<std::chrono::microseconds>(
                  x1_dequeue_start.time_since_epoch()).count()
            : 0;
    if (x1_dequeue_log) {
        LOG_INFO(Service_Nvnflinger,
                 "[X1-DEQUEUE][BEGIN] hostUs={} callUs={} core=0x{:x} async={} width={} height={} format={} usage={}",
                 x1_dequeue_call_us, x1_dequeue_call_us,
                 reinterpret_cast<std::uintptr_t>(core.get()), async, width, height,
                 static_cast<u32>(format), usage);
    }

'''
    producer_text = replace_once(
        producer_text, dequeue_prefix, dequeue_prefix_replacement, "DequeueBuffer begin timing"
    )

    slot_anchor = '''        s32 found{};
        Status status = WaitForFreeSlotThenRelock(async, &found, &return_flags, lock);
        if (status != Status::NoError) {
            return status;
        }

'''
    slot_replacement = '''        s32 found{};
        const auto x1_slot_wait_start =
            x1_dequeue_log ? std::chrono::steady_clock::now()
                           : std::chrono::steady_clock::time_point{};
        Status status = WaitForFreeSlotThenRelock(async, &found, &return_flags, lock);
        const auto x1_slot_wait_end =
            x1_dequeue_log ? std::chrono::steady_clock::now()
                           : std::chrono::steady_clock::time_point{};
        if (x1_dequeue_log) {
            const auto x1_slot_wait_us = std::chrono::duration_cast<std::chrono::microseconds>(
                x1_slot_wait_end - x1_slot_wait_start).count();
            const auto x1_pre_slot_us = std::chrono::duration_cast<std::chrono::microseconds>(
                x1_slot_wait_start - x1_dequeue_start).count();
            const auto x1_slot_host_us = std::chrono::duration_cast<std::chrono::microseconds>(
                x1_slot_wait_end.time_since_epoch()).count();
            LOG_INFO(Service_Nvnflinger,
                     "[X1-DEQUEUE][SLOT] hostUs={} callUs={} core=0x{:x} slot={} status={} preSlotUs={} slotWaitUs={}",
                     x1_slot_host_us, x1_dequeue_call_us,
                     reinterpret_cast<std::uintptr_t>(core.get()), found, status,
                     x1_pre_slot_us, x1_slot_wait_us);
        }
        if (status != Status::NoError) {
            return status;
        }

'''
    producer_text = replace_once(
        producer_text, slot_anchor, slot_replacement, "DequeueBuffer free-slot timing"
    )

    return_anchor = '''    LOG_DEBUG(Service_Nvnflinger, "returning slot={} frame={}, flags={}", *out_slot,
              slots[*out_slot].frame_number, return_flags);

    return return_flags;
}
'''
    return_replacement = '''    LOG_DEBUG(Service_Nvnflinger, "returning slot={} frame={}, flags={}", *out_slot,
              slots[*out_slot].frame_number, return_flags);

    if (x1_dequeue_log) {
        const auto x1_dequeue_end = std::chrono::steady_clock::now();
        const auto x1_dequeue_host_us = std::chrono::duration_cast<std::chrono::microseconds>(
            x1_dequeue_end.time_since_epoch()).count();
        const auto x1_dequeue_total_us = std::chrono::duration_cast<std::chrono::microseconds>(
            x1_dequeue_end - x1_dequeue_start).count();
        LOG_INFO(Service_Nvnflinger,
                 "[X1-DEQUEUE][END] hostUs={} callUs={} core=0x{:x} slot={} frame={} flags={} totalUs={}",
                 x1_dequeue_host_us, x1_dequeue_call_us,
                 reinterpret_cast<std::uintptr_t>(core.get()), *out_slot,
                 slots[*out_slot].frame_number, return_flags, x1_dequeue_total_us);
    }

    return return_flags;
}
'''
    producer_text = replace_once(
        producer_text, return_anchor, return_replacement, "DequeueBuffer return timing"
    )
    producer.write_text(producer_text, encoding="utf-8")

    composer = root / "src/core/hle/service/nvnflinger/hardware_composer.cpp"
    composer_text = composer.read_text(encoding="utf-8")
    cadence_gate = "Settings::values.x1_present_frame_log.GetValue()"
    if composer_text.count(cadence_gate) != 2:
        raise RuntimeError(
            f"composer cadence gate: expected 2 parent uses, got {composer_text.count(cadence_gate)}"
        )
    composer_text = composer_text.replace(
        cadence_gate, "Settings::values.x1_frame_cadence_log.GetValue()"
    )
    composer.write_text(composer_text, encoding="utf-8")

    producer_final = producer.read_text(encoding="utf-8")
    wait_helper_after = extract_between(
        producer_final,
        "Status BufferQueueProducer::WaitForFreeSlotThenRelock(",
        "Status BufferQueueProducer::DequeueBuffer(",
        "WaitForFreeSlotThenRelock helper after",
    )
    if wait_helper_after != wait_helper_before:
        raise RuntimeError("Dequeue helper semantics changed; harness must be observation-only")

    for required in (
        "[X1-DEQUEUE][BEGIN]",
        "[X1-DEQUEUE][SLOT]",
        "[X1-DEQUEUE][END]",
        "[X1-CADENCE][QUEUE]",
        "WaitForFreeSlotThenRelock(async, &found, &return_flags, lock);",
        "core->WaitWhileAllocatingLocked();",
        "item.swap_interval = swap_interval;",
        "listener_available->OnFrameAvailable(item)",
    ):
        if required not in producer_final:
            raise RuntimeError(f"producer harness invariant missing: {required}")

    composer_final = composer.read_text(encoding="utf-8")
    for required in (
        "[X1-CADENCE][ACQUIRE]",
        "[X1-CADENCE][VI]",
        "effective={}",
        "X1EffectiveMainSwapInterval(fb_it->second.item.swap_interval)",
        "X1EffectiveMainSwapInterval(framebuffer.item.swap_interval)",
        "nvdisp.WaitForComposite();",
        "nvdisp.Composite(composition_stack);",
        "m_frame_number += 1;",
        "return 1;",
    ):
        if required not in composer_final:
            raise RuntimeError(f"composer harness invariant missing: {required}")

    if "Settings::values.x1_present_frame_log.GetValue()" in composer_final:
        raise RuntimeError("old present-frame gate remains in HardwareComposer cadence instrumentation")

    final_settings = settings.read_text(encoding="utf-8")
    for required in ("x1_frame_cadence_log", "x1_dequeue_attribution_log"):
        if required not in final_settings:
            raise RuntimeError(f"new diagnostic setting missing: {required}")

    print("Applied X1 exact-dc95 runtime-selectable diagnostic harness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
