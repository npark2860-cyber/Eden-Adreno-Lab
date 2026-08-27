#!/usr/bin/env python3
'''Add a single Qualcomm/X1 A/B switch for exact-dc95 adaptive Uniform fast streaming.

Expected order:
  - transplant_dc95_draw_dispatch_ab_controls.py
  - transplant_dc95_uniform_payload_fingerprint.py
  - this pass

OFF preserves exact existing behavior. ON changes only the adaptive small-Uniform fast-stream
selection on Qualcomm proprietary Vulkan: alignment-required Uniforms still stream, while an
otherwise fastSkip-eligible Uniform falls through to the existing classic cached path.

This experiment does not add payload reuse/dedupe and does not alter SynchronizeBuffer(), dirty
tracking, staging/descriptor lifetime, barriers, render-pass behavior, scheduler behavior, aliasing,
or non-Uniform buffer paths.
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
        raise SystemExit("usage: transplant_dc95_uniform_cache_ab.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # Require the exact parent experiment chain before changing behavior.
    generic = root / "src/video_core/buffer_cache/buffer_cache.h"
    generic_text = generic.read_text(encoding="utf-8")
    for marker in (
        "const bool use_fast_buffer = needs_alignment_stream",
        "x1_uniform_payload_sampled",
        "P::RecordX1UniformPath",
        "const bool x1_uniform_cached_clean = SynchronizeBuffer(buffer, device_addr, size);",
    ):
        if marker not in generic_text:
            raise RuntimeError(f"payload-fingerprint parent marker missing: {marker}")

    # ------------------------------------------------------------------
    # Persisted debug setting. Default OFF is the exact payload baseline.
    # ------------------------------------------------------------------
    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    settings_anchor = '''    Setting<u64> x1_ab_dispatch_signature{linkage, 0, "x1_ab_dispatch_signature",\n                                          Category::Debugging};\n'''
    text = replace_once(
        text,
        settings_anchor,
        settings_anchor
        + '''    Setting<bool> x1_ab_disable_adaptive_uniform_fast_stream{\n        linkage, false, "x1_ab_disable_adaptive_uniform_fast_stream", Category::Debugging};\n''',
        "Uniform cache A/B setting",
    )
    settings.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Qt debug checkbox. Existing debug controls are runtime-locked.
    # ------------------------------------------------------------------
    header = root / "src/yuzu/configuration/configure_debug.h"
    text = header.read_text(encoding="utf-8")
    member_anchor = '''    QCheckBox* x1_ab_skip_dispatch_checkbox{};\n    QLineEdit* x1_ab_dispatch_signature_edit{};\n\n    const Core::System& system;\n'''
    text = replace_once(
        text,
        member_anchor,
        '''    QCheckBox* x1_ab_skip_dispatch_checkbox{};\n    QLineEdit* x1_ab_dispatch_signature_edit{};\n    QCheckBox* x1_ab_disable_adaptive_uniform_fast_stream_checkbox{};\n\n    const Core::System& system;\n''',
        "Uniform cache A/B widget member",
    )
    header.write_text(text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = cpp.read_text(encoding="utf-8")

    construction_anchor = '''    x1_ab_dispatch_signature_edit = new QLineEdit(this);\n    x1_ab_dispatch_signature_edit->setPlaceholderText(tr("Dispatch signature (hex)"));\n\n'''
    text = replace_once(
        text,
        construction_anchor,
        construction_anchor
        + '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox =\n        new QCheckBox(tr("X1 A/B: Disable Adaptive Uniform Fast Stream"), this);\n\n''',
        "Uniform cache A/B widget construction",
    )

    tooltip_anchor = '''    x1_ab_skip_dispatch_checkbox->setToolTip(\n        tr("EXPERIMENT: skip only Dispatch calls whose correlation signature exactly matches the "\n           "hex value. Disabled by default."));\n\n'''
    text = replace_once(
        text,
        tooltip_anchor,
        tooltip_anchor
        + '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setToolTip(\n        tr("EXPERIMENT: on Qualcomm Vulkan only, disable adaptive small-Uniform fast streaming "\n           "while preserving alignment-required streaming. Disabled by default."));\n\n''',
        "Uniform cache A/B tooltip",
    )

    layout_anchor = '''    ui->gridLayout_1->addWidget(x1_ab_skip_dispatch_checkbox, 5, 2);\n    ui->gridLayout_1->addWidget(x1_ab_dispatch_signature_edit, 5, 3);\n\n'''
    text = replace_once(
        text,
        layout_anchor,
        layout_anchor
        + '''    ui->gridLayout_1->addWidget(x1_ab_disable_adaptive_uniform_fast_stream_checkbox,\n                                6, 2, 1, 2);\n\n''',
        "Uniform cache A/B widget layout",
    )

    state_anchor = '''    x1_ab_dispatch_signature_edit->setText(\n        QString::number(Settings::values.x1_ab_dispatch_signature.GetValue(), 16).toUpper());\n'''
    text = replace_once(
        text,
        state_anchor,
        state_anchor
        + '''    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setEnabled(runtime_lock);\n    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setChecked(\n        Settings::values.x1_ab_disable_adaptive_uniform_fast_stream.GetValue());\n''',
        "Uniform cache A/B widget state",
    )

    apply_anchor = '''    Settings::values.x1_ab_dispatch_signature = x1_dispatch_sig_ok ? x1_dispatch_sig : 0;\n'''
    text = replace_once(
        text,
        apply_anchor,
        apply_anchor
        + '''    Settings::values.x1_ab_disable_adaptive_uniform_fast_stream =\n        x1_ab_disable_adaptive_uniform_fast_stream_checkbox->isChecked();\n''',
        "Uniform cache A/B widget apply",
    )

    retranslate_anchor = '''    x1_ab_dispatch_signature_edit->setPlaceholderText(tr("Dispatch signature (hex)"));\n}\n'''
    text = replace_once(
        text,
        retranslate_anchor,
        '''    x1_ab_dispatch_signature_edit->setPlaceholderText(tr("Dispatch signature (hex)"));\n    x1_ab_disable_adaptive_uniform_fast_stream_checkbox->setText(\n        tr("X1 A/B: Disable Adaptive Uniform Fast Stream"));\n}\n''',
        "Uniform cache A/B widget retranslate",
    )
    cpp.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Vulkan-only cached policy bit. Resolve driver + setting once when the
    # BufferCacheRuntime is constructed, avoiding per-Uniform settings reads.
    # ------------------------------------------------------------------
    vk_header = vulkan / "vk_buffer_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    method_anchor = '''    u32 GetUniformBufferAlignment() const;\n\n    u32 GetStorageBufferAlignment() const;\n'''
    text = replace_once(
        text,
        method_anchor,
        '''    u32 GetUniformBufferAlignment() const;\n\n    bool ShouldDisableAdaptiveUniformFastStream() const noexcept {\n        return disable_adaptive_uniform_fast_stream;\n    }\n\n    u32 GetStorageBufferAlignment() const;\n''',
        "Vulkan Uniform cache A/B policy accessor",
    )
    member_anchor = '''    bool limit_dynamic_storage_buffers = false;\n    u32 max_dynamic_storage_buffers = (std::numeric_limits<u32>::max)();\n'''
    text = replace_once(
        text,
        member_anchor,
        '''    bool disable_adaptive_uniform_fast_stream = false;\n    bool limit_dynamic_storage_buffers = false;\n    u32 max_dynamic_storage_buffers = (std::numeric_limits<u32>::max)();\n''',
        "Vulkan Uniform cache A/B policy state",
    )
    vk_header.write_text(text, encoding="utf-8")

    vk_cpp = vulkan / "vk_buffer_cache.cpp"
    text = vk_cpp.read_text(encoding="utf-8")
    include_anchor = '''#include <vector>\n\n#include "video_core/buffer_cache/buffer_cache_base.h"\n'''
    text = replace_once(
        text,
        include_anchor,
        '''#include <vector>\n\n#include "common/settings.h"\n#include "video_core/buffer_cache/buffer_cache_base.h"\n''',
        "settings include for Uniform cache A/B",
    )
    driver_anchor = '''    const VkDriverIdKHR driver_id = device.GetDriverID();\n    limit_dynamic_storage_buffers = driver_id == VK_DRIVER_ID_QUALCOMM_PROPRIETARY ||\n'''
    text = replace_once(
        text,
        driver_anchor,
        '''    const VkDriverIdKHR driver_id = device.GetDriverID();\n    disable_adaptive_uniform_fast_stream =\n        driver_id == VK_DRIVER_ID_QUALCOMM_PROPRIETARY &&\n        Settings::values.x1_ab_disable_adaptive_uniform_fast_stream.GetValue();\n    limit_dynamic_storage_buffers = driver_id == VK_DRIVER_ID_QUALCOMM_PROPRIETARY ||\n''',
        "Qualcomm Uniform cache A/B policy initialization",
    )
    vk_cpp.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Change only adaptive fastSkip selection. Alignment-required streaming
    # remains authoritative. The existing fast body and classic cached body
    # are intentionally untouched.
    # ------------------------------------------------------------------
    text = generic_text
    decision_anchor = '''    const bool use_fast_buffer = needs_alignment_stream\n        || (has_host_buffer && size <= channel_state->uniform_buffer_skip_cache_size\n            && !memory_tracker.IsRegionGpuModified(device_addr, size));\n'''
    decision_replacement = '''    const bool x1_adaptive_fast_eligible =\n        has_host_buffer && size <= channel_state->uniform_buffer_skip_cache_size &&\n        !memory_tracker.IsRegionGpuModified(device_addr, size);\n    bool x1_disable_adaptive_uniform_fast_stream = false;\n    if constexpr (!IS_OPENGL) {\n        x1_disable_adaptive_uniform_fast_stream =\n            runtime.ShouldDisableAdaptiveUniformFastStream();\n    }\n    const bool use_fast_buffer =\n        needs_alignment_stream ||\n        (x1_adaptive_fast_eligible && !x1_disable_adaptive_uniform_fast_stream);\n'''
    text = replace_once(
        text,
        decision_anchor,
        decision_replacement,
        "adaptive Uniform fast-stream A/B gate",
    )
    generic.write_text(text, encoding="utf-8")

    # Static invariants local to this transplant.
    final_generic = generic.read_text(encoding="utf-8")
    for required in (
        "needs_alignment_stream ||",
        "x1_adaptive_fast_eligible && !x1_disable_adaptive_uniform_fast_stream",
        "runtime.ShouldDisableAdaptiveUniformFastStream()",
        "device_memory.ReadBlockUnsafe(device_addr, span.data(), size)",
        "const bool x1_uniform_cached_clean = SynchronizeBuffer(buffer, device_addr, size);",
        "HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS",
    ):
        if required not in final_generic:
            raise RuntimeError(f"Uniform cache A/B invariant missing: {required}")

    for forbidden_path in (
        root / "src/video_core/renderer_vulkan/vk_scheduler.cpp",
        root / "src/video_core/renderer_vulkan/vk_scheduler.h",
    ):
        if not forbidden_path.exists():
            raise RuntimeError(f"expected baseline file missing: {forbidden_path}")

    print("Applied X1 exact-dc95 Qualcomm adaptive Uniform cache A/B control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
