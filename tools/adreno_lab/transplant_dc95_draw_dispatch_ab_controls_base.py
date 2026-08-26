#!/usr/bin/env python3
"""Add UI-controlled signature A/B gates to the exact-dc95 Draw/Dispatch experiment.

Expected order:
  - full-flow controls/transplants
  - exact dc95 finalizer
  - transplant_dc95_draw_dispatch_correlation.py

All A/B controls default OFF. With them off, guest Draw/Dispatch work is unchanged.
When explicitly enabled, only an exact matching signature is skipped before its expensive
preparation path. This is a diagnostic A/B control, not a production optimization.
"""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_draw_dispatch_ab_controls.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # ------------------------------------------------------------------
    # Persisted settings: all behavioral A/B controls default OFF.
    # ------------------------------------------------------------------
    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = (
        '    Setting<bool> x1_qcom_workaround_log{linkage, false, "x1_qcom_workaround_log",\n'
        '                                         Category::Debugging};\n'
    )
    text = replace_once(
        text,
        anchor,
        anchor
        + '    Setting<bool> x1_ab_skip_draw{linkage, false, "x1_ab_skip_draw", Category::Debugging};\n'
          '    Setting<u64> x1_ab_draw_signature{linkage, 0, "x1_ab_draw_signature",\n'
          '                                      Category::Debugging};\n'
          '    Setting<bool> x1_ab_skip_dispatch{linkage, false, "x1_ab_skip_dispatch",\n'
          '                                       Category::Debugging};\n'
          '    Setting<u64> x1_ab_dispatch_signature{linkage, 0, "x1_ab_dispatch_signature",\n'
          '                                          Category::Debugging};\n',
        "A/B settings",
    )
    settings.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Qt controls. Existing debug controls are already runtime-locked.
    # ------------------------------------------------------------------
    header = root / "src/yuzu/configuration/configure_debug.h"
    text = header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'class QCheckBox;\nclass QSpinBox;\n',
        'class QCheckBox;\nclass QLineEdit;\nclass QSpinBox;\n',
        "QLineEdit forward declaration",
    )
    text = replace_once(
        text,
        '''    QCheckBox* x1_qcom_workaround_log_checkbox{};\n\n    const Core::System& system;\n''',
        '''    QCheckBox* x1_qcom_workaround_log_checkbox{};\n    QCheckBox* x1_ab_skip_draw_checkbox{};\n    QLineEdit* x1_ab_draw_signature_edit{};\n    QCheckBox* x1_ab_skip_dispatch_checkbox{};\n    QLineEdit* x1_ab_dispatch_signature_edit{};\n\n    const Core::System& system;\n''',
        "A/B widget members",
    )
    header.write_text(text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include <QCheckBox>\n#include <QDesktopServices>\n',
        '#include <QCheckBox>\n#include <QDesktopServices>\n#include <QLineEdit>\n',
        "QLineEdit include",
    )

    construction_anchor = '''    x1_qcom_workaround_log_checkbox =\n        new QCheckBox(tr("X1 Log: QCOM Workaround Hits"), this);\n\n'''
    construction = construction_anchor + '''    x1_ab_skip_draw_checkbox =\n        new QCheckBox(tr("X1 A/B: Skip Matching Draw"), this);\n    x1_ab_draw_signature_edit = new QLineEdit(this);\n    x1_ab_draw_signature_edit->setPlaceholderText(tr("Draw signature (hex)"));\n    x1_ab_skip_dispatch_checkbox =\n        new QCheckBox(tr("X1 A/B: Skip Matching Dispatch"), this);\n    x1_ab_dispatch_signature_edit = new QLineEdit(this);\n    x1_ab_dispatch_signature_edit->setPlaceholderText(tr("Dispatch signature (hex)"));\n\n'''
    text = replace_once(text, construction_anchor, construction, "A/B widget construction")

    tooltip_anchor = '''    x1_qcom_workaround_log_checkbox->setToolTip(\n        tr("Count key Qualcomm-specific policy/workaround paths used at runtime. Disabled "\n           "by default."));\n\n'''
    tooltip = tooltip_anchor + '''    x1_ab_skip_draw_checkbox->setToolTip(\n        tr("EXPERIMENT: skip only Draw calls whose correlation signature exactly matches the hex "\n           "value. Disabled by default."));\n    x1_ab_skip_dispatch_checkbox->setToolTip(\n        tr("EXPERIMENT: skip only Dispatch calls whose correlation signature exactly matches the "\n           "hex value. Disabled by default."));\n\n'''
    text = replace_once(text, tooltip_anchor, tooltip, "A/B tooltips")

    layout_anchor = '''    ui->gridLayout_1->addWidget(x1_qcom_workaround_log_checkbox, 4, 0, 1, 2);\n\n'''
    layout = layout_anchor + '''    ui->gridLayout_1->addWidget(x1_ab_skip_draw_checkbox, 4, 2);\n    ui->gridLayout_1->addWidget(x1_ab_draw_signature_edit, 4, 3);\n    ui->gridLayout_1->addWidget(x1_ab_skip_dispatch_checkbox, 5, 2);\n    ui->gridLayout_1->addWidget(x1_ab_dispatch_signature_edit, 5, 3);\n\n'''
    text = replace_once(text, layout_anchor, layout, "A/B widget layout")

    state_anchor = '''    x1_qcom_workaround_log_checkbox->setChecked(\n        Settings::values.x1_qcom_workaround_log.GetValue());\n'''
    state = state_anchor + '''    x1_ab_skip_draw_checkbox->setEnabled(runtime_lock);\n    x1_ab_draw_signature_edit->setEnabled(runtime_lock);\n    x1_ab_skip_dispatch_checkbox->setEnabled(runtime_lock);\n    x1_ab_dispatch_signature_edit->setEnabled(runtime_lock);\n    x1_ab_skip_draw_checkbox->setChecked(Settings::values.x1_ab_skip_draw.GetValue());\n    x1_ab_draw_signature_edit->setText(\n        QString::number(Settings::values.x1_ab_draw_signature.GetValue(), 16).toUpper());\n    x1_ab_skip_dispatch_checkbox->setChecked(Settings::values.x1_ab_skip_dispatch.GetValue());\n    x1_ab_dispatch_signature_edit->setText(\n        QString::number(Settings::values.x1_ab_dispatch_signature.GetValue(), 16).toUpper());\n'''
    text = replace_once(text, state_anchor, state, "A/B widget state")

    apply_anchor = '''    Settings::values.x1_qcom_workaround_log =\n        x1_qcom_workaround_log_checkbox->isChecked();\n'''
    apply = apply_anchor + '''    Settings::values.x1_ab_skip_draw = x1_ab_skip_draw_checkbox->isChecked();\n    bool x1_draw_sig_ok{};\n    const u64 x1_draw_sig = x1_ab_draw_signature_edit->text().toULongLong(&x1_draw_sig_ok, 16);\n    Settings::values.x1_ab_draw_signature = x1_draw_sig_ok ? x1_draw_sig : 0;\n    Settings::values.x1_ab_skip_dispatch = x1_ab_skip_dispatch_checkbox->isChecked();\n    bool x1_dispatch_sig_ok{};\n    const u64 x1_dispatch_sig =\n        x1_ab_dispatch_signature_edit->text().toULongLong(&x1_dispatch_sig_ok, 16);\n    Settings::values.x1_ab_dispatch_signature = x1_dispatch_sig_ok ? x1_dispatch_sig : 0;\n'''
    text = replace_once(text, apply_anchor, apply, "A/B widget apply")

    retranslate_anchor = '''    x1_qcom_workaround_log_checkbox->setText(tr("X1 Log: QCOM Workaround Hits"));\n}\n'''
    retranslate = '''    x1_qcom_workaround_log_checkbox->setText(tr("X1 Log: QCOM Workaround Hits"));\n    x1_ab_skip_draw_checkbox->setText(tr("X1 A/B: Skip Matching Draw"));\n    x1_ab_draw_signature_edit->setPlaceholderText(tr("Draw signature (hex)"));\n    x1_ab_skip_dispatch_checkbox->setText(tr("X1 A/B: Skip Matching Dispatch"));\n    x1_ab_dispatch_signature_edit->setPlaceholderText(tr("Dispatch signature (hex)"));\n}\n'''
    text = replace_once(text, retranslate_anchor, retranslate, "A/B widget retranslate")
    cpp.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Exact signature gates in RasterizerVulkan.
    # ------------------------------------------------------------------
    rasterizer = vulkan / "vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")

    # Keep DrawTexture out of the Draw/Dispatch experiment. It is a separate blit path.
    correlated_draw_texture = '''void RasterizerVulkan::DrawTexture() {\n    auto& x1_origin_profiler = AdrenoProfiler::Get();\n    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Draw);\n    x1_origin_profiler.SetWorkSignature(1ULL << 60);\n    SCOPE_EXIT {\n        x1_origin_profiler.EndWork();\n        gpu.TickWork();\n    };\n'''
    original_draw_texture = '''void RasterizerVulkan::DrawTexture() {\n\n    SCOPE_EXIT {\n        gpu.TickWork();\n    };\n'''
    text = replace_once(text, correlated_draw_texture, original_draw_texture, "exclude DrawTexture")

    draw_prefix = '''void RasterizerVulkan::Draw(bool is_indexed, u32 instance_count) {\n    PrepareDraw(is_indexed, [this, is_indexed, instance_count] {\n        const auto& draw_state = maxwell3d->draw_manager.draw_state;\n        const u32 num_instances{instance_count};\n        const DrawParams draw_params{MakeDrawParams(draw_state, num_instances, is_indexed)};\n        const u64 draw_signature =\n            (static_cast<u64>(is_indexed) << 63) |\n            ((static_cast<u64>(draw_state.topology) & 0xFFULL) << 55) |\n            ((static_cast<u64>(draw_params.num_instances) & 0x7FFFFFULL) << 32) |\n            static_cast<u64>(draw_params.num_vertices);\n        AdrenoProfiler::Get().SetWorkSignature(draw_signature);\n\n'''
    draw_replacement = '''void RasterizerVulkan::Draw(bool is_indexed, u32 instance_count) {\n    const auto& x1_ab_draw_state = maxwell3d->draw_manager.draw_state;\n    const u32 x1_ab_raw_vertices =\n        is_indexed ? x1_ab_draw_state.index_buffer.count : x1_ab_draw_state.vertex_buffer.count;\n    const u64 draw_signature =\n        (static_cast<u64>(is_indexed) << 63) |\n        ((static_cast<u64>(x1_ab_draw_state.topology) & 0xFFULL) << 55) |\n        ((static_cast<u64>(instance_count) & 0x7FFFFFULL) << 32) |\n        static_cast<u64>(x1_ab_raw_vertices);\n    if (device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY &&\n        Settings::values.x1_ab_skip_draw.GetValue() &&\n        Settings::values.x1_ab_draw_signature.GetValue() == draw_signature) {\n        LOG_INFO(Render_Vulkan, "[X1-FLOW][AB] kind=draw sig=0x{:016X} action=skip",\n                 draw_signature);\n        gpu.TickWork();\n        return;\n    }\n    PrepareDraw(is_indexed, [this, is_indexed, instance_count, draw_signature] {\n        const auto& draw_state = maxwell3d->draw_manager.draw_state;\n        const u32 num_instances{instance_count};\n        const DrawParams draw_params{MakeDrawParams(draw_state, num_instances, is_indexed)};\n        AdrenoProfiler::Get().SetWorkSignature(draw_signature);\n\n'''
    text = replace_once(text, draw_prefix, draw_replacement, "direct Draw A/B gate")

    indirect_prefix = '''void RasterizerVulkan::DrawIndirect() {\n    const auto& params = maxwell3d->draw_manager.indirect_state;\n    buffer_cache.SetDrawIndirect(&params);\n    PrepareDraw(params.is_indexed, [this, &params] {\n        const u64 draw_signature =\n            (1ULL << 62) | (static_cast<u64>(params.is_indexed) << 61) |\n            ((static_cast<u64>(params.max_draw_counts) & 0x1FFFFFFFULL) << 32) |\n            (static_cast<u64>(params.stride) & 0xFFFFFFFFULL);\n        AdrenoProfiler::Get().SetWorkSignature(draw_signature);\n'''
    indirect_replacement = '''void RasterizerVulkan::DrawIndirect() {\n    const auto& params = maxwell3d->draw_manager.indirect_state;\n    const u64 draw_signature =\n        (1ULL << 62) | (static_cast<u64>(params.is_indexed) << 61) |\n        ((static_cast<u64>(params.max_draw_counts) & 0x1FFFFFFFULL) << 32) |\n        (static_cast<u64>(params.stride) & 0xFFFFFFFFULL);\n    if (device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY &&\n        Settings::values.x1_ab_skip_draw.GetValue() &&\n        Settings::values.x1_ab_draw_signature.GetValue() == draw_signature) {\n        LOG_INFO(Render_Vulkan, "[X1-FLOW][AB] kind=draw-indirect sig=0x{:016X} action=skip",\n                 draw_signature);\n        gpu.TickWork();\n        return;\n    }\n    buffer_cache.SetDrawIndirect(&params);\n    PrepareDraw(params.is_indexed, [this, &params, draw_signature] {\n        AdrenoProfiler::Get().SetWorkSignature(draw_signature);\n'''
    text = replace_once(text, indirect_prefix, indirect_replacement, "indirect Draw A/B gate")

    dispatch_prefix = '''void RasterizerVulkan::DispatchCompute() {\n    auto& x1_origin_profiler = AdrenoProfiler::Get();\n    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Dispatch);\n    SCOPE_EXIT {\n        x1_origin_profiler.EndWork();\n    };\n    FlushWork();\n'''
    dispatch_replacement = '''void RasterizerVulkan::DispatchCompute() {\n    const auto& x1_ab_qmd = kepler_compute->launch_description;\n    const auto x1_ab_indirect_address = kepler_compute->GetIndirectComputeAddress();\n    const u64 dispatch_signature = x1_ab_indirect_address\n        ? ((1ULL << 63) |\n           (static_cast<u64>(*x1_ab_indirect_address) & 0x7FFFFFFFFFFFFFFFULL))\n        : ((static_cast<u64>(x1_ab_qmd.grid_dim_x) & 0x1FFFFFULL) |\n           ((static_cast<u64>(x1_ab_qmd.grid_dim_y) & 0x1FFFFFULL) << 21) |\n           ((static_cast<u64>(x1_ab_qmd.grid_dim_z) & 0x1FFFFFULL) << 42));\n    if (device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY &&\n        Settings::values.x1_ab_skip_dispatch.GetValue() &&\n        Settings::values.x1_ab_dispatch_signature.GetValue() == dispatch_signature) {\n        LOG_INFO(Render_Vulkan, "[X1-FLOW][AB] kind=dispatch sig=0x{:016X} action=skip",\n                 dispatch_signature);\n        return;\n    }\n    auto& x1_origin_profiler = AdrenoProfiler::Get();\n    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Dispatch);\n    x1_origin_profiler.SetWorkSignature(dispatch_signature);\n    SCOPE_EXIT {\n        x1_origin_profiler.EndWork();\n    };\n    FlushWork();\n'''
    text = replace_once(text, dispatch_prefix, dispatch_replacement, "Dispatch A/B gate")

    indirect_dispatch_signature = '''        x1_origin_profiler.SetWorkSignature(\n            (1ULL << 63) | (static_cast<u64>(*indirect_address) & 0x7FFFFFFFFFFFFFFFULL));\n'''
    text = replace_once(text, indirect_dispatch_signature, "", "remove duplicate indirect signature")

    direct_dispatch_signature = '''    const u64 dispatch_signature =\n        (static_cast<u64>(dim[0]) & 0x1FFFFFULL) |\n        ((static_cast<u64>(dim[1]) & 0x1FFFFFULL) << 21) |\n        ((static_cast<u64>(dim[2]) & 0x1FFFFFULL) << 42);\n    x1_origin_profiler.SetWorkSignature(dispatch_signature);\n'''
    text = replace_once(text, direct_dispatch_signature, "", "remove duplicate direct signature")

    rasterizer.write_text(text, encoding="utf-8")

    print("Transplanted exact dc95 signature-based Draw/Dispatch A/B controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
