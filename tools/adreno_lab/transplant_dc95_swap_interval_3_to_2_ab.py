#!/usr/bin/env python3
'''Add an X1 diagnostic A/B that clamps main-layer effective swap interval 3 to 2.

Expected order:
  - recreate the existing diagnostic chain through Uniform cache A/B
  - transplant_dc95_frame_cadence_attribution.py
  - this pass

OFF preserves the observed raw guest/main-layer behavior.
ON preserves the raw QueueBuffer parcel/item value and only changes the HardwareComposer's
main non-overlay effective acquire/release interval from exactly 3 to 2.

This is an attribution A/B, not a production fix. It does not change the guest parcel, QueueBuffer
item assignment, VI base clock, speed limiter, Vulkan present mode, scheduler, fences, barriers,
render-pass handling, Uniform policy, alias path, overlays, or intervals other than raw 3.

The HardwareComposer service layer does not own Vulkan driver identity, so this diagnostic branch
uses a strict Windows ARM64 + Vulkan + explicit checkbox guard. The workflow itself is dedicated to
the X1/Qualcomm lab target and the checkbox defaults OFF.
'''

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_swap_interval_3_to_2_ab.py <eden-root>")

    root = Path(sys.argv[1])

    # Require the cadence diagnostic parent state.
    producer = root / "src/core/hle/service/nvnflinger/buffer_queue_producer.cpp"
    producer_text = producer.read_text(encoding="utf-8")
    for marker in (
        "[X1-CADENCE][QUEUE]",
        "item.swap_interval = swap_interval;",
        "listener_available->OnFrameAvailable(item)",
    ):
        if marker not in producer_text:
            raise RuntimeError(f"cadence parent producer marker missing: {marker}")

    composer = root / "src/core/hle/service/nvnflinger/hardware_composer.cpp"
    composer_text = composer.read_text(encoding="utf-8")
    for marker in (
        "[X1-CADENCE][ACQUIRE]",
        "[X1-CADENCE][VI]",
        "NormalizeSwapInterval(nullptr, fb_it->second.item.swap_interval)",
        "NormalizeSwapInterval(nullptr, framebuffer.item.swap_interval)",
        "return 1;",
    ):
        if marker not in composer_text:
            raise RuntimeError(f"cadence parent composer marker missing: {marker}")

    # ------------------------------------------------------------------
    # Persisted debug setting, default OFF.
    # ------------------------------------------------------------------
    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    settings_anchor = '''    Setting<bool> x1_ab_disable_adaptive_uniform_fast_stream{\n        linkage, false, "x1_ab_disable_adaptive_uniform_fast_stream", Category::Debugging};\n'''
    text = replace_once(
        text,
        settings_anchor,
        settings_anchor
        + '''    Setting<bool> x1_ab_clamp_main_swap_interval_3_to_2{\n        linkage, false, "x1_ab_clamp_main_swap_interval_3_to_2", Category::Debugging};\n''',
        "swap interval A/B setting",
    )
    settings.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Qt debug checkbox, runtime-locked like the existing X1 A/B controls.
    # ------------------------------------------------------------------
    header = root / "src/yuzu/configuration/configure_debug.h"
    text = header.read_text(encoding="utf-8")
    member_anchor = '''    QCheckBox* x1_ab_disable_adaptive_uniform_fast_stream_checkbox{};\n\n    const Core::System& system;\n'''
    text = replace_once(
        text,
        member_anchor,
        '''    QCheckBox* x1_ab_disable_adaptive_uniform_fast_stream_checkbox{};\n    QCheckBox* x1_ab_clamp_main_swap_interval_3_to_2_checkbox{};\n\n    const Core::System& system;\n''',
        "swap interval A/B widget member",
    )
    header.write_text(text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = cpp.read_text(encoding="utf-8")

    construction_anchor = '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox =\n        new QCheckBox(tr("X1 A/B: Disable Adaptive Uniform Fast Stream"), this);\n\n'''
    text = replace_once(
        text,
        construction_anchor,
        construction_anchor
        + '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox =\n        new QCheckBox(tr("X1 A/B: Clamp Main Swap Interval 3 To 2"), this);\n\n''',
        "swap interval A/B widget construction",
    )

    tooltip_anchor = '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setToolTip(\n        tr("EXPERIMENT: on Qualcomm Vulkan only, disable adaptive small-Uniform fast streaming "\n           "while preserving alignment-required streaming. Disabled by default."));\n\n'''
    text = replace_once(
        text,
        tooltip_anchor,
        tooltip_anchor
        + '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setToolTip(\n        tr("EXPERIMENT: in the X1 Windows ARM64 Vulkan diagnostic build, preserve raw guest "\n           "swap=3 but use effective main-layer acquire/release interval 2. Disabled by default."));\n\n''',
        "swap interval A/B tooltip",
    )

    layout_anchor = '''    ui->gridLayout_1->addWidget(x1_ab_disable_adaptive_uniform_fast_stream_checkbox,\n                                6, 2, 1, 2);\n\n'''
    text = replace_once(
        text,
        layout_anchor,
        layout_anchor
        + '''    ui->gridLayout_1->addWidget(x1_ab_clamp_main_swap_interval_3_to_2_checkbox,\n                                7, 2, 1, 2);\n\n''',
        "swap interval A/B widget layout",
    )

    state_anchor = '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setChecked(\n        Settings::values.x1_ab_disable_adaptive_uniform_fast_stream.GetValue());\n'''
    text = replace_once(
        text,
        state_anchor,
        state_anchor
        + '''    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setEnabled(runtime_lock);\n    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setChecked(\n        Settings::values.x1_ab_clamp_main_swap_interval_3_to_2.GetValue());\n''',
        "swap interval A/B widget state",
    )

    apply_anchor = '''    Settings::values.x1_ab_disable_adaptive_uniform_fast_stream =\n        x1_ab_disable_adaptive_uniform_fast_stream_checkbox->isChecked();\n'''
    text = replace_once(
        text,
        apply_anchor,
        apply_anchor
        + '''    Settings::values.x1_ab_clamp_main_swap_interval_3_to_2 =\n        x1_ab_clamp_main_swap_interval_3_to_2_checkbox->isChecked();\n''',
        "swap interval A/B widget apply",
    )

    retranslate_anchor = '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setText(\n        tr("X1 A/B: Disable Adaptive Uniform Fast Stream"));\n}\n'''
    text = replace_once(
        text,
        retranslate_anchor,
        '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setText(\n        tr("X1 A/B: Disable Adaptive Uniform Fast Stream"));\n    x1_ab_clamp_main_swap_interval_3_to_2_checkbox->setText(\n        tr("X1 A/B: Clamp Main Swap Interval 3 To 2"));\n}\n''',
        "swap interval A/B widget retranslate",
    )
    cpp.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # HardwareComposer-only effective policy.
    # Raw BufferItem::swap_interval remains untouched.
    # ------------------------------------------------------------------
    text = composer_text
    helper_anchor = '''s32 NormalizeSwapInterval(f32* out_speed_scale, s32 swap_interval) {\n'''
    if helper_anchor not in text:
        raise RuntimeError("NormalizeSwapInterval helper missing")

    namespace_anchor = '''    return swap_interval;\n}\n\n} // namespace\n'''
    namespace_replacement = '''    return swap_interval;\n}\n\ns32 X1EffectiveMainSwapInterval(s32 raw_swap_interval) {\n    const s32 normalized = NormalizeSwapInterval(nullptr, raw_swap_interval);\n#if defined(_WIN32) && (defined(_M_ARM64) || defined(__aarch64__))\n    const bool x1_clamp_enabled =\n        Settings::values.renderer_backend.GetValue() == Settings::RendererBackend::Vulkan &&\n        Settings::values.x1_ab_clamp_main_swap_interval_3_to_2.GetValue();\n    if (x1_clamp_enabled && raw_swap_interval == 3) {\n        return 2;\n    }\n#endif\n    return normalized;\n}\n\n} // namespace\n'''
    text = replace_once(
        text,
        namespace_anchor,
        namespace_replacement,
        "effective swap helper",
    )

    expected_anchor = '''                const s32 expected_interval = NormalizeSwapInterval(nullptr, fb_it->second.item.swap_interval);\n'''
    text = replace_once(
        text,
        expected_anchor,
        '''                const s32 expected_interval =\n                    X1EffectiveMainSwapInterval(fb_it->second.item.swap_interval);\n''',
        "effective acquire interval",
    )

    release_anchor = '''    const s32 swap_interval = layer.is_overlay ? 1 : NormalizeSwapInterval(nullptr, framebuffer.item.swap_interval);\n'''
    text = replace_once(
        text,
        release_anchor,
        '''    const s32 swap_interval =\n        layer.is_overlay ? 1 : X1EffectiveMainSwapInterval(framebuffer.item.swap_interval);\n''',
        "effective release interval",
    )

    acquire_log_anchor = '''                LOG_INFO(Service_Nvnflinger,\n                         "[X1-CADENCE][ACQUIRE] hostUs={} tick={} consumer={} overlay={} frame={} swap={}",\n                         x1_acquire_host_us, m_frame_number, consumer_id, layer->is_overlay,\n                         item.frame_number, item.swap_interval);\n'''
    acquire_log_replacement = '''                const s32 x1_effective_swap_interval =\n                    layer->is_overlay ? 1 : X1EffectiveMainSwapInterval(item.swap_interval);\n                LOG_INFO(Service_Nvnflinger,\n                         "[X1-CADENCE][ACQUIRE] hostUs={} tick={} consumer={} overlay={} frame={} swap={} effective={}",\n                         x1_acquire_host_us, m_frame_number, consumer_id, layer->is_overlay,\n                         item.frame_number, item.swap_interval, x1_effective_swap_interval);\n'''
    text = replace_once(
        text,
        acquire_log_anchor,
        acquire_log_replacement,
        "effective interval acquire logging",
    )
    composer.write_text(text, encoding="utf-8")

    # Static invariants.
    final_producer = producer.read_text(encoding="utf-8")
    final_composer = composer.read_text(encoding="utf-8")
    final_settings = settings.read_text(encoding="utf-8")

    if "item.swap_interval = swap_interval;" not in final_producer:
        raise RuntimeError("raw QueueBuffer swap assignment changed or disappeared")
    if "x1_ab_clamp_main_swap_interval_3_to_2" not in final_settings:
        raise RuntimeError("swap interval A/B setting missing")
    for required in (
        "X1EffectiveMainSwapInterval(fb_it->second.item.swap_interval)",
        "X1EffectiveMainSwapInterval(framebuffer.item.swap_interval)",
        "raw_swap_interval == 3",
        "return 2;",
        "[X1-CADENCE][ACQUIRE]",
        "effective={}",
        "nvdisp.WaitForComposite();",
        "nvdisp.Composite(composition_stack);",
        "m_frame_number += 1;",
        "return 1;",
    ):
        if required not in final_composer:
            raise RuntimeError(f"swap interval A/B invariant missing: {required}")

    print("Applied X1 exact-dc95 main swap interval 3->2 attribution A/B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
