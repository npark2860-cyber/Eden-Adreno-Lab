#!/usr/bin/env python3
"""Add explicit Qt checkbox controls for dc95 diagnostic/GPU log outputs.

This is intentionally a separate transplant from the descriptor-ring instrumentation so
control/source semantics remain easy to audit. It runs after the descriptor profiler transplant.
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
        raise SystemExit("usage: transplant_dc95_logging_checkboxes.py <eden-root>")

    root = Path(sys.argv[1])

    # 1) Persistent OFF-by-default switch for the X1 descriptor-ring diagnostic log.
    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    Setting<bool> gpu_log_driver_debug{linkage, true, "gpu_log_driver_debug", Category::Debugging};\n',
        '    Setting<bool> gpu_log_driver_debug{linkage, true, "gpu_log_driver_debug", Category::Debugging};\n'
        '    Setting<bool> x1_descriptor_ring_log{linkage, false, "x1_descriptor_ring_log",\n'
        '                                         Category::Debugging};\n',
        "settings X1 descriptor log toggle",
    )
    settings.write_text(text, encoding="utf-8")

    # 2) Store programmatically-created checkboxes in ConfigureDebug.
    header = root / "src/yuzu/configuration/configure_debug.h"
    text = header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'class QSpinBox;\n',
        'class QCheckBox;\nclass QSpinBox;\n',
        "ConfigureDebug QCheckBox forward declaration",
    )
    text = replace_once(
        text,
        '    std::unique_ptr<Ui::ConfigureDebug> ui;\n\n    const Core::System& system;\n',
        '    std::unique_ptr<Ui::ConfigureDebug> ui;\n\n'
        '    QCheckBox* gpu_log_vulkan_calls_checkbox{};\n'
        '    QCheckBox* gpu_log_memory_tracking_checkbox{};\n'
        '    QCheckBox* gpu_log_driver_debug_checkbox{};\n'
        '    QCheckBox* x1_descriptor_ring_log_checkbox{};\n\n'
        '    const Core::System& system;\n',
        "ConfigureDebug checkbox members",
    )
    header.write_text(text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include <QDesktopServices>\n',
        '#include <QCheckBox>\n#include <QDesktopServices>\n',
        "ConfigureDebug QCheckBox include",
    )
    text = replace_once(
        text,
        '    ui->setupUi(this);\n    SetConfiguration();\n',
        '    ui->setupUi(this);\n\n'
        '    gpu_log_vulkan_calls_checkbox = new QCheckBox(tr("GPU Log: Vulkan Calls"), this);\n'
        '    gpu_log_memory_tracking_checkbox =\n'
        '        new QCheckBox(tr("GPU Log: Memory Tracking"), this);\n'
        '    gpu_log_driver_debug_checkbox = new QCheckBox(tr("GPU Log: Driver Debug"), this);\n'
        '    x1_descriptor_ring_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Descriptor Ring"), this);\n'
        '    x1_descriptor_ring_log_checkbox->setToolTip(\n'
        '        tr("Log descriptor allocations, frame-slot waits, chunk switches, and forced "\n'
        '           "Scheduler::Finish stalls. Disabled by default."));\n\n'
        '    ui->gridLayout_1->addWidget(gpu_log_vulkan_calls_checkbox, 2, 0);\n'
        '    ui->gridLayout_1->addWidget(gpu_log_memory_tracking_checkbox, 2, 1);\n'
        '    ui->gridLayout_1->addWidget(gpu_log_driver_debug_checkbox, 2, 2);\n'
        '    ui->gridLayout_1->addWidget(x1_descriptor_ring_log_checkbox, 2, 3);\n\n'
        '    SetConfiguration();\n',
        "ConfigureDebug checkbox construction",
    )
    text = replace_once(
        text,
        '    ui->gpu_log_shader_dumps->setEnabled(runtime_lock);\n'
        '    ui->gpu_log_shader_dumps->setChecked(Settings::values.gpu_log_shader_dumps.GetValue());\n',
        '    ui->gpu_log_shader_dumps->setEnabled(runtime_lock);\n'
        '    ui->gpu_log_shader_dumps->setChecked(Settings::values.gpu_log_shader_dumps.GetValue());\n'
        '    gpu_log_vulkan_calls_checkbox->setEnabled(runtime_lock);\n'
        '    gpu_log_vulkan_calls_checkbox->setChecked(\n'
        '        Settings::values.gpu_log_vulkan_calls.GetValue());\n'
        '    gpu_log_memory_tracking_checkbox->setEnabled(runtime_lock);\n'
        '    gpu_log_memory_tracking_checkbox->setChecked(\n'
        '        Settings::values.gpu_log_memory_tracking.GetValue());\n'
        '    gpu_log_driver_debug_checkbox->setEnabled(runtime_lock);\n'
        '    gpu_log_driver_debug_checkbox->setChecked(\n'
        '        Settings::values.gpu_log_driver_debug.GetValue());\n'
        '    x1_descriptor_ring_log_checkbox->setEnabled(runtime_lock);\n'
        '    x1_descriptor_ring_log_checkbox->setChecked(\n'
        '        Settings::values.x1_descriptor_ring_log.GetValue());\n',
        "ConfigureDebug checkbox state",
    )
    text = replace_once(
        text,
        '    Settings::values.gpu_log_shader_dumps = ui->gpu_log_shader_dumps->isChecked();\n'
        '    Debugger::ToggleConsole();\n',
        '    Settings::values.gpu_log_shader_dumps = ui->gpu_log_shader_dumps->isChecked();\n'
        '    Settings::values.gpu_log_vulkan_calls = gpu_log_vulkan_calls_checkbox->isChecked();\n'
        '    Settings::values.gpu_log_memory_tracking =\n'
        '        gpu_log_memory_tracking_checkbox->isChecked();\n'
        '    Settings::values.gpu_log_driver_debug = gpu_log_driver_debug_checkbox->isChecked();\n'
        '    Settings::values.x1_descriptor_ring_log =\n'
        '        x1_descriptor_ring_log_checkbox->isChecked();\n'
        '    Debugger::ToggleConsole();\n',
        "ConfigureDebug checkbox apply",
    )
    text = replace_once(
        text,
        'void ConfigureDebug::RetranslateUI() {\n    ui->retranslateUi(this);\n}\n',
        'void ConfigureDebug::RetranslateUI() {\n'
        '    ui->retranslateUi(this);\n'
        '    gpu_log_vulkan_calls_checkbox->setText(tr("GPU Log: Vulkan Calls"));\n'
        '    gpu_log_memory_tracking_checkbox->setText(tr("GPU Log: Memory Tracking"));\n'
        '    gpu_log_driver_debug_checkbox->setText(tr("GPU Log: Driver Debug"));\n'
        '    x1_descriptor_ring_log_checkbox->setText(tr("X1 Log: Descriptor Ring"));\n'
        '}\n',
        "ConfigureDebug checkbox retranslate",
    )
    cpp.write_text(text, encoding="utf-8")

    # 3) Make the X1 profiler's enable decision come only from the persisted checkbox.
    #    The environment variable remains only for report cadence, not for on/off control.
    profiler = root / "src/video_core/renderer_vulkan/vk_descriptor_ring_profiler.cpp"
    text = profiler.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "common/logging.h"\n',
        '#include "common/logging.h"\n#include "common/settings.h"\n',
        "descriptor profiler settings include",
    )
    old_parse = '''bool DescriptorRingProfiler::ParseEnabled() {
    const char* const raw = std::getenv("EDEN_X1_DESCRIPTOR_PROFILE");
    if (!raw) {
        return false;
    }
    const std::string_view value{raw};
    return value == "1" || value == "true" || value == "TRUE" || value == "on" ||
           value == "ON";
}
'''
    new_parse = '''bool DescriptorRingProfiler::ParseEnabled() {
    return Settings::values.x1_descriptor_ring_log.GetValue();
}
'''
    text = replace_once(text, old_parse, new_parse, "descriptor profiler checkbox enable")
    profiler.write_text(text, encoding="utf-8")

    print("Transplanted dc95 diagnostic logging checkboxes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
