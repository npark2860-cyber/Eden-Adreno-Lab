#!/usr/bin/env python3
"""Add checkbox controls and full-flow hooks to an exact dc95 Eden checkout.

Expected order:
  - broad P0/P0.2 source patches already applied from Eden-Adreno-Lab
  - vk_adreno_profiler.{h,cpp} copied from the full-flow branch
  - descriptor-ring profiler transplant applied
  - base logging checkboxes transplant applied
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
        raise SystemExit("usage: transplant_dc95_full_flow_hooks.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # 1) OFF-by-default settings.
    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = (
        '    Setting<bool> x1_descriptor_ring_log{linkage, false, "x1_descriptor_ring_log",\n'
        '                                         Category::Debugging};\n'
    )
    text = replace_once(
        text,
        anchor,
        anchor
        + '    Setting<bool> x1_scheduler_sync_log{linkage, false, "x1_scheduler_sync_log",\n'
          '                                        Category::Debugging};\n'
          '    Setting<bool> x1_present_frame_log{linkage, false, "x1_present_frame_log",\n'
          '                                       Category::Debugging};\n'
          '    Setting<bool> x1_pipeline_shader_log{linkage, false, "x1_pipeline_shader_log",\n'
          '                                         Category::Debugging};\n'
          '    Setting<bool> x1_upload_barrier_log{linkage, false, "x1_upload_barrier_log",\n'
          '                                        Category::Debugging};\n'
          '    Setting<bool> x1_qcom_workaround_log{linkage, false, "x1_qcom_workaround_log",\n'
          '                                         Category::Debugging};\n',
        "full-flow settings",
    )
    settings.write_text(text, encoding="utf-8")

    # 2) Qt checkboxes.
    header = root / "src/yuzu/configuration/configure_debug.h"
    text = header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    QCheckBox* x1_descriptor_ring_log_checkbox{};\n\n    const Core::System& system;\n',
        '    QCheckBox* x1_descriptor_ring_log_checkbox{};\n'
        '    QCheckBox* x1_scheduler_sync_log_checkbox{};\n'
        '    QCheckBox* x1_present_frame_log_checkbox{};\n'
        '    QCheckBox* x1_pipeline_shader_log_checkbox{};\n'
        '    QCheckBox* x1_upload_barrier_log_checkbox{};\n'
        '    QCheckBox* x1_qcom_workaround_log_checkbox{};\n\n'
        '    const Core::System& system;\n',
        "ConfigureDebug full-flow members",
    )
    header.write_text(text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = cpp.read_text(encoding="utf-8")
    anchor = (
        '    x1_descriptor_ring_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Descriptor Ring"), this);\n'
        '    x1_descriptor_ring_log_checkbox->setToolTip(\n'
        '        tr("Log descriptor allocations, frame-slot waits, chunk switches, and forced "\n'
        '           "Scheduler::Finish stalls. Disabled by default."));\n\n'
        '    ui->gridLayout_1->addWidget(gpu_log_vulkan_calls_checkbox, 2, 0);\n'
        '    ui->gridLayout_1->addWidget(gpu_log_memory_tracking_checkbox, 2, 1);\n'
        '    ui->gridLayout_1->addWidget(gpu_log_driver_debug_checkbox, 2, 2);\n'
        '    ui->gridLayout_1->addWidget(x1_descriptor_ring_log_checkbox, 2, 3);\n\n'
    )
    replacement = (
        '    x1_descriptor_ring_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Descriptor Ring"), this);\n'
        '    x1_scheduler_sync_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Scheduler / Sync"), this);\n'
        '    x1_present_frame_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Present / Frame Pacing"), this);\n'
        '    x1_pipeline_shader_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Pipeline / Shader"), this);\n'
        '    x1_upload_barrier_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: Upload / Barrier"), this);\n'
        '    x1_qcom_workaround_log_checkbox =\n'
        '        new QCheckBox(tr("X1 Log: QCOM Workaround Hits"), this);\n\n'
        '    x1_descriptor_ring_log_checkbox->setToolTip(\n'
        '        tr("Log descriptor allocations, frame-slot waits, chunk switches, and forced "\n'
        '           "Scheduler::Finish stalls. Disabled by default."));\n'
        '    x1_scheduler_sync_log_checkbox->setToolTip(\n'
        '        tr("Log Scheduler waits, Finish/WaitWorker, submits, render-pass flow, and slow "\n'
        '           "synchronization events. Disabled by default."));\n'
        '    x1_present_frame_log_checkbox->setToolTip(\n'
        '        tr("Log free-frame/fence waits, swapchain acquire/present, and frame-pacing waits. "\n'
        '           "Disabled by default."));\n'
        '    x1_pipeline_shader_log_checkbox->setToolTip(\n'
        '        tr("Log graphics/compute pipeline build time and SPIR-V emission time. Disabled by "\n'
        '           "default."));\n'
        '    x1_upload_barrier_log_checkbox->setToolTip(\n'
        '        tr("Log staging traffic, buffer-copy bytes, and key upload/copy barriers. Disabled "\n'
        '           "by default."));\n'
        '    x1_qcom_workaround_log_checkbox->setToolTip(\n'
        '        tr("Count key Qualcomm-specific policy/workaround paths used at runtime. Disabled "\n'
        '           "by default."));\n\n'
        '    ui->gridLayout_1->addWidget(gpu_log_vulkan_calls_checkbox, 2, 0);\n'
        '    ui->gridLayout_1->addWidget(gpu_log_memory_tracking_checkbox, 2, 1);\n'
        '    ui->gridLayout_1->addWidget(gpu_log_driver_debug_checkbox, 2, 2);\n'
        '    ui->gridLayout_1->addWidget(x1_descriptor_ring_log_checkbox, 2, 3);\n'
        '    ui->gridLayout_1->addWidget(x1_scheduler_sync_log_checkbox, 3, 0);\n'
        '    ui->gridLayout_1->addWidget(x1_present_frame_log_checkbox, 3, 1);\n'
        '    ui->gridLayout_1->addWidget(x1_pipeline_shader_log_checkbox, 3, 2);\n'
        '    ui->gridLayout_1->addWidget(x1_upload_barrier_log_checkbox, 3, 3);\n'
        '    ui->gridLayout_1->addWidget(x1_qcom_workaround_log_checkbox, 4, 0, 1, 2);\n\n'
    )
    text = replace_once(text, anchor, replacement, "ConfigureDebug full-flow construction")

    anchor = (
        '    x1_descriptor_ring_log_checkbox->setEnabled(runtime_lock);\n'
        '    x1_descriptor_ring_log_checkbox->setChecked(\n'
        '        Settings::values.x1_descriptor_ring_log.GetValue());\n'
    )
    text = replace_once(
        text,
        anchor,
        anchor
        + '    x1_scheduler_sync_log_checkbox->setEnabled(runtime_lock);\n'
          '    x1_scheduler_sync_log_checkbox->setChecked(\n'
          '        Settings::values.x1_scheduler_sync_log.GetValue());\n'
          '    x1_present_frame_log_checkbox->setEnabled(runtime_lock);\n'
          '    x1_present_frame_log_checkbox->setChecked(\n'
          '        Settings::values.x1_present_frame_log.GetValue());\n'
          '    x1_pipeline_shader_log_checkbox->setEnabled(runtime_lock);\n'
          '    x1_pipeline_shader_log_checkbox->setChecked(\n'
          '        Settings::values.x1_pipeline_shader_log.GetValue());\n'
          '    x1_upload_barrier_log_checkbox->setEnabled(runtime_lock);\n'
          '    x1_upload_barrier_log_checkbox->setChecked(\n'
          '        Settings::values.x1_upload_barrier_log.GetValue());\n'
          '    x1_qcom_workaround_log_checkbox->setEnabled(runtime_lock);\n'
          '    x1_qcom_workaround_log_checkbox->setChecked(\n'
          '        Settings::values.x1_qcom_workaround_log.GetValue());\n',
        "ConfigureDebug full-flow state",
    )

    anchor = (
        '    Settings::values.x1_descriptor_ring_log =\n'
        '        x1_descriptor_ring_log_checkbox->isChecked();\n'
    )
    text = replace_once(
        text,
        anchor,
        anchor
        + '    Settings::values.x1_scheduler_sync_log =\n'
          '        x1_scheduler_sync_log_checkbox->isChecked();\n'
          '    Settings::values.x1_present_frame_log =\n'
          '        x1_present_frame_log_checkbox->isChecked();\n'
          '    Settings::values.x1_pipeline_shader_log =\n'
          '        x1_pipeline_shader_log_checkbox->isChecked();\n'
          '    Settings::values.x1_upload_barrier_log =\n'
          '        x1_upload_barrier_log_checkbox->isChecked();\n'
          '    Settings::values.x1_qcom_workaround_log =\n'
          '        x1_qcom_workaround_log_checkbox->isChecked();\n',
        "ConfigureDebug full-flow apply",
    )

    text = replace_once(
        text,
        '    x1_descriptor_ring_log_checkbox->setText(tr("X1 Log: Descriptor Ring"));\n}\n',
        '    x1_descriptor_ring_log_checkbox->setText(tr("X1 Log: Descriptor Ring"));\n'
        '    x1_scheduler_sync_log_checkbox->setText(tr("X1 Log: Scheduler / Sync"));\n'
        '    x1_present_frame_log_checkbox->setText(tr("X1 Log: Present / Frame Pacing"));\n'
        '    x1_pipeline_shader_log_checkbox->setText(tr("X1 Log: Pipeline / Shader"));\n'
        '    x1_upload_barrier_log_checkbox->setText(tr("X1 Log: Upload / Barrier"));\n'
        '    x1_qcom_workaround_log_checkbox->setText(tr("X1 Log: QCOM Workaround Hits"));\n'
        '}\n',
        "ConfigureDebug full-flow retranslate",
    )
    cpp.write_text(text, encoding="utf-8")

    # 3) Register central profiler and shared frame id.
    cmake = root / "src/video_core/CMakeLists.txt"
    text = cmake.read_text(encoding="utf-8")
    anchor = (
        "    renderer_vulkan/vk_descriptor_ring_profiler.cpp\n"
        "    renderer_vulkan/vk_descriptor_ring_profiler.h\n"
    )
    text = replace_once(
        text,
        anchor,
        anchor
        + "    renderer_vulkan/vk_adreno_profiler.cpp\n"
          "    renderer_vulkan/vk_adreno_profiler.h\n",
        "CMake central profiler registration",
    )
    cmake.write_text(text, encoding="utf-8")

    renderer = vulkan / "renderer_vulkan.cpp"
    text = renderer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n',
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        "renderer profiler include",
    )
    init_anchor = (
        "    DescriptorRingProfiler::Get().Initialize(\n"
        "        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);\n\n"
    )
    text = replace_once(
        text,
        init_anchor,
        init_anchor
        + "    AdrenoProfiler::Get().Initialize(\n"
          "        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);\n\n",
        "renderer central profiler init",
    )
    text = replace_once(
        text,
        "    DescriptorRingProfiler::Get().FrameEnd();\n}",
        "    DescriptorRingProfiler::Get().FrameEnd();\n"
        "    AdrenoProfiler::Get().FrameEnd();\n}",
        "renderer central profiler frame end",
    )
    renderer.write_text(text, encoding="utf-8")

    # 4) Scheduler: every Wait + existing broad timers.
    scheduler_h = vulkan / "vk_scheduler.h"
    text = scheduler_h.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_master_semaphore.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_master_semaphore.h"\n',
        "scheduler profiler include",
    )
    start = text.index("    /// Waits for the given GPU tick, optionally pacing frames.\n")
    end = text.index("    /// Returns the master timeline semaphore.\n", start)
    old_block = text[start:end]
    func_start = old_block.index("    void Wait(u64 tick, double target_fps = 0.0) {")
    comment = old_block[:func_start]
    new_func = '''    void Wait(u64 tick, double target_fps = 0.0) {
        auto& profiler = AdrenoProfiler::Get();
        const bool profile_wait = profiler.SchedulerEnabled();
        u64 gpu_wait_ns{};
        u64 pacing_wait_ns{};
        bool forced_flush{};
        if (tick > 0) {
            forced_flush = tick >= master_semaphore->CurrentTick();
            if (forced_flush) {
                Flush();
            }
            const auto gpu_start = profile_wait ? AdrenoProfiler::Now() : AdrenoProfiler::TimePoint{};
            master_semaphore->Wait(tick);
            if (profile_wait) {
                gpu_wait_ns = AdrenoProfiler::ElapsedNs(gpu_start);
            }
        }
        const auto pacing_start = profile_wait ? AdrenoProfiler::Now() : AdrenoProfiler::TimePoint{};
        if (Settings::values.use_speed_limit.GetValue() && target_fps > 0.0) {
            auto now = std::chrono::steady_clock::now();
            if (last_target_fps != target_fps) {
                frame_interval = std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(1.0 / target_fps));
                max_frame_count = static_cast<int>(0.1 * target_fps);
                last_target_fps = target_fps;
                frame_counter = 0;
                start_time = now;
            }
            frame_counter++;
            auto target_time = start_time + frame_interval * frame_counter;
            if (target_time >= now) {
                constexpr auto spin_tail = std::chrono::milliseconds(1);
                auto sleep_time = target_time - now;
                if (sleep_time > spin_tail * 2) {
                    std::this_thread::sleep_for(sleep_time - spin_tail);
                }
                while (std::chrono::steady_clock::now() < target_time) {
                    std::this_thread::yield();
                }
            } else if (frame_counter > max_frame_count) {
                frame_counter = 0;
                start_time = now;
            }
        }
        if (profile_wait) {
            pacing_wait_ns = AdrenoProfiler::ElapsedNs(pacing_start);
            profiler.RecordSchedulerWait(tick, forced_flush, gpu_wait_ns, pacing_wait_ns);
        }
    }

'''
    text = text[:start] + comment + new_func + text[end:]
    scheduler_h.write_text(text, encoding="utf-8")

    scheduler_cpp = vulkan / "vk_scheduler.cpp"
    text = scheduler_cpp.read_text(encoding="utf-8")
    text = text.replace("profiler.Enabled()", "profiler.SchedulerEnabled()")
    barrier = "        upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);\n"
    if barrier in text:
        text = replace_once(
            text,
            barrier,
            barrier + '        AdrenoProfiler::Get().RecordBarrier("submit-upload", 1);\n',
            "submit upload barrier accounting",
        )
    scheduler_cpp.write_text(text, encoding="utf-8")

    for filename in ("vk_graphics_pipeline.cpp", "vk_compute_pipeline.cpp"):
        path = vulkan / filename
        text = path.read_text(encoding="utf-8")
        text = text.replace("profiler.Enabled()", "profiler.PipelineEnabled()")
        path.write_text(text, encoding="utf-8")

    # 5) SPIR-V emission + QCOM shader profile.
    pipeline_cache = vulkan / "vk_pipeline_cache.cpp"
    text = pipeline_cache.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_compute_pipeline.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_compute_pipeline.h"\n',
        "pipeline cache profiler include",
    )
    gfx = '        const std::vector<u32> code{EmitSPIRV(profile, runtime_info, program, binding)};\n'
    text = replace_once(
        text,
        gfx,
        '        auto& x1_profiler = AdrenoProfiler::Get();\n'
        '        const auto x1_emit_start = x1_profiler.PipelineEnabled() ? AdrenoProfiler::Now()\n'
        '                                                                  : AdrenoProfiler::TimePoint{};\n'
        + gfx
        + '        if (x1_profiler.PipelineEnabled()) {\n'
          '            x1_profiler.RecordShaderEmit("graphics-spirv",\n'
          '                                         AdrenoProfiler::ElapsedNs(x1_emit_start),\n'
          '                                         static_cast<u64>(code.size() * sizeof(u32)));\n'
          '        }\n',
        "graphics SPIR-V timer",
    )
    comp = '    const std::vector<u32> code{EmitSPIRV(profile, program)};\n'
    text = replace_once(
        text,
        comp,
        '    auto& x1_profiler = AdrenoProfiler::Get();\n'
        '    const auto x1_emit_start = x1_profiler.PipelineEnabled() ? AdrenoProfiler::Now()\n'
        '                                                              : AdrenoProfiler::TimePoint{};\n'
        + comp
        + '    if (x1_profiler.PipelineEnabled()) {\n'
          '        x1_profiler.RecordShaderEmit("compute-spirv",\n'
          '                                     AdrenoProfiler::ElapsedNs(x1_emit_start),\n'
          '                                     static_cast<u64>(code.size() * sizeof(u32)));\n'
          '    }\n',
        "compute SPIR-V timer",
    )
    driver = '    const VkDriverId driver_id{device.GetDriverID()};\n'
    text = replace_once(
        text,
        driver,
        driver
        + '    if (driver_id == VK_DRIVER_ID_QUALCOMM_PROPRIETARY) {\n'
          '        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::ShaderProfile);\n'
          '    }\n',
        "QCOM shader profile hit",
    )
    pipeline_cache.write_text(text, encoding="utf-8")

    # 6) Present and frame-pacing waits.
    present = vulkan / "vk_present_manager.cpp"
    text = present.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_present_manager.h"\n',
        '#include "video_core/renderer_vulkan/vk_present_manager.h"\n'
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        "present manager profiler include",
    )
    text = replace_once(
        text,
        '    std::unique_lock lock{free_mutex};\n    free_cv.wait(lock, [this] { return !free_queue.empty(); });\n',
        '    std::unique_lock lock{free_mutex};\n'
        '    auto& profiler = AdrenoProfiler::Get();\n'
        '    const auto free_wait_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()\n'
        '                                                            : AdrenoProfiler::TimePoint{};\n'
        '    free_cv.wait(lock, [this] { return !free_queue.empty(); });\n'
        '    if (profiler.PresentEnabled()) {\n'
        '        profiler.RecordPresentWait("free-frame", AdrenoProfiler::ElapsedNs(free_wait_start));\n'
        '    }\n',
        "free frame wait",
    )
    text = replace_once(
        text,
        '    frame->present_done.Wait();\n    frame->present_done.Reset();\n',
        '    const auto fence_wait_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()\n'
        '                                                             : AdrenoProfiler::TimePoint{};\n'
        '    frame->present_done.Wait();\n'
        '    if (profiler.PresentEnabled()) {\n'
        '        profiler.RecordPresentWait("present-fence",\n'
        '                                   AdrenoProfiler::ElapsedNs(fence_wait_start));\n'
        '    }\n'
        '    frame->present_done.Reset();\n',
        "present fence wait",
    )
    text = replace_once(
        text,
        '        std::unique_lock queue_lock{queue_mutex};\n        frame_cv.wait(queue_lock, [this] { return present_queue.empty(); });\n',
        '        std::unique_lock queue_lock{queue_mutex};\n'
        '        auto& profiler = AdrenoProfiler::Get();\n'
        '        const auto queue_wait_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()\n'
        '                                                                 : AdrenoProfiler::TimePoint{};\n'
        '        frame_cv.wait(queue_lock, [this] { return present_queue.empty(); });\n'
        '        if (profiler.PresentEnabled()) {\n'
        '            profiler.RecordPresentWait("present-queue-drain",\n'
        '                                       AdrenoProfiler::ElapsedNs(queue_wait_start));\n'
        '        }\n',
        "present queue drain wait",
    )
    present.write_text(text, encoding="utf-8")

    swapchain = vulkan / "vk_swapchain.cpp"
    text = swapchain.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_scheduler.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_scheduler.h"\n',
        "swapchain profiler include",
    )
    acquire = '''    const VkResult result = device.GetLogical().AcquireNextImageKHR(
        *swapchain, (std::numeric_limits<u64>::max)(), *present_semaphores[frame_index],
        VK_NULL_HANDLE, &image_index);
'''
    text = replace_once(
        text,
        acquire,
        '''    auto& profiler = AdrenoProfiler::Get();
    const auto acquire_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()
                                                         : AdrenoProfiler::TimePoint{};
    const VkResult result = device.GetLogical().AcquireNextImageKHR(
        *swapchain, (std::numeric_limits<u64>::max)(), *present_semaphores[frame_index],
        VK_NULL_HANDLE, &image_index);
    if (profiler.PresentEnabled()) {
        profiler.RecordAcquire(AdrenoProfiler::ElapsedNs(acquire_start), static_cast<int>(result));
    }
''',
        "swapchain acquire",
    )
    text = replace_once(
        text,
        '    const auto wait_with_frame_pacing = [this] {\n    switch (Settings::values.frame_pacing_mode.GetValue()) {\n',
        '    const auto wait_with_frame_pacing = [this] {\n'
        '    auto& profiler = AdrenoProfiler::Get();\n'
        '    const auto pacing_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()\n'
        '                                                        : AdrenoProfiler::TimePoint{};\n'
        '    switch (Settings::values.frame_pacing_mode.GetValue()) {\n',
        "swapchain pacing start",
    )
    text = replace_once(
        text,
        '    }\n    };\n\n#ifdef __ANDROID__\n',
        '    }\n'
        '    if (profiler.PresentEnabled()) {\n'
        '        profiler.RecordPresentWait("swapchain-resource-pacing",\n'
        '                                   AdrenoProfiler::ElapsedNs(pacing_start));\n'
        '    }\n'
        '    };\n\n#ifdef __ANDROID__\n',
        "swapchain pacing end",
    )
    text = replace_once(
        text,
        '    switch (const VkResult result = present_queue.Present(present_info)) {\n',
        '    auto& profiler = AdrenoProfiler::Get();\n'
        '    const auto present_start = profiler.PresentEnabled() ? AdrenoProfiler::Now()\n'
        '                                                         : AdrenoProfiler::TimePoint{};\n'
        '    const VkResult present_result = present_queue.Present(present_info);\n'
        '    if (profiler.PresentEnabled()) {\n'
        '        profiler.RecordPresentCall(AdrenoProfiler::ElapsedNs(present_start),\n'
        '                                   static_cast<int>(present_result));\n'
        '    }\n'
        '    switch (present_result) {\n',
        "swapchain present",
    )
    swapchain.write_text(text, encoding="utf-8")

    # 7) Barrier counts + QCOM dynamic-storage limiter.
    buffer_cache = vulkan / "vk_buffer_cache.cpp"
    text = buffer_cache.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_buffer_cache.h"\n',
        '#include "video_core/renderer_vulkan/vk_buffer_cache.h"\n'
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        "buffer cache profiler include",
    )
    text = replace_once(
        text,
        'void BufferCacheRuntime::PreCopyBarrier() {\n',
        'void BufferCacheRuntime::PreCopyBarrier() {\n'
        '    AdrenoProfiler::Get().RecordBarrier("buffer-pre-copy", 1);\n',
        "pre copy barrier",
    )
    text = replace_once(
        text,
        'void BufferCacheRuntime::PostCopyBarrier() {\n',
        'void BufferCacheRuntime::PostCopyBarrier() {\n'
        '    AdrenoProfiler::Get().RecordBarrier("buffer-post-copy", 1);\n',
        "post copy barrier",
    )
    qcom_anchor = (
        '    if (limit_dynamic_storage_buffers) {\n'
        '        max_dynamic_storage_buffers = device.GetMaxDescriptorSetStorageBuffersDynamic();\n'
        '    }    \n'
    )
    text = replace_once(
        text,
        qcom_anchor,
        qcom_anchor
        + '    if (driver_id == VK_DRIVER_ID_QUALCOMM_PROPRIETARY) {\n'
          '        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::DynamicStorageLimit);\n'
          '    }\n',
        "QCOM dynamic storage limiter",
    )
    buffer_cache.write_text(text, encoding="utf-8")

    # 8) Descriptor shared frame id, stalls, and tiler policy.
    descriptor = vulkan / "vk_descriptor_buffer.cpp"
    text = descriptor.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n',
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        "descriptor central profiler include",
    )
    frame_size = '    const VkDeviceSize frame_size{device.IsTiler() ? TILER_FRAME_SIZE : DESKTOP_FRAME_SIZE};\n'
    text = replace_once(
        text,
        frame_size,
        frame_size
        + '    if (device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY) {\n'
          '        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::DescriptorTilerPolicy);\n'
          '    }\n',
        "QCOM descriptor tiler policy",
    )
    text = replace_once(
        text,
        '            profiler.RecordFrameReuseWait(DescriptorRingProfiler::ElapsedNs(wait_start));\n',
        '            const u64 wait_ns = DescriptorRingProfiler::ElapsedNs(wait_start);\n'
        '            profiler.RecordFrameReuseWait(wait_ns);\n'
        '            AdrenoProfiler::Get().RecordDescriptorStall(\n'
        '                "descriptor-slot-reuse", frame_ticks[frame_index], wait_ns);\n',
        "descriptor reuse correlation",
    )
    text = replace_once(
        text,
        '                profiler.RecordExhaustionFinish(\n'
        '                    DescriptorRingProfiler::ElapsedNs(finish_start));\n',
        '                const u64 finish_ns = DescriptorRingProfiler::ElapsedNs(finish_start);\n'
        '                profiler.RecordExhaustionFinish(finish_ns);\n'
        '                AdrenoProfiler::Get().RecordDescriptorStall(\n'
        '                    "descriptor-exhaustion-finish", scheduler.CurrentTick(), finish_ns);\n',
        "descriptor finish correlation",
    )
    descriptor.write_text(text, encoding="utf-8")

    dbuf = vulkan / "vk_descriptor_ring_profiler.cpp"
    text = dbuf.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n',
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        "descriptor summary frame include",
    )
    text = replace_once(
        text,
        '             "[X1-DBUF] frames={} | alloc={} bytes={} ({:.1f} KiB/f) | reuseWait={} "\n',
        '             "[X1-DBUF] frame={} frames={} | alloc={} bytes={} ({:.1f} KiB/f) | reuseWait={} "\n',
        "descriptor summary frame format",
    )
    text = replace_once(
        text,
        '             frames, allocations, allocation_bytes, PerFrame(ToKiB(allocation_bytes), frames),\n',
        '             AdrenoProfiler::Get().CurrentFrame(), frames, allocations, allocation_bytes,\n'
        '             PerFrame(ToKiB(allocation_bytes), frames),\n',
        "descriptor summary frame arg",
    )
    dbuf.write_text(text, encoding="utf-8")

    # 9) Runtime QCOM sampler-path hits.
    texture = vulkan / "vk_texture_cache.cpp"
    text = texture.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_texture_cache.h"\n',
        '#include "video_core/renderer_vulkan/vk_texture_cache.h"\n'
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        "texture profiler include",
    )
    text = replace_once(
        text,
        '    if (has_custom_border_colors) {\n        pnext = &border_ci;\n',
        '    if (has_custom_border_colors) {\n'
        '        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::CustomBorderColor);\n'
        '        pnext = &border_ci;\n',
        "custom border hit",
    )
    text = replace_once(
        text,
        '    if (device.IsExtBorderColorSwizzleSupported() && GPU::Logging::IsActive()) {\n',
        '    if (device.IsExtBorderColorSwizzleSupported()) {\n'
        '        AdrenoProfiler::Get().RecordQcomHit(AdrenoProfiler::QcomEvent::BorderColorSwizzle);\n'
        '    }\n'
        '    if (device.IsExtBorderColorSwizzleSupported() && GPU::Logging::IsActive()) {\n',
        "border swizzle hit",
    )
    texture.write_text(text, encoding="utf-8")

    print("Transplanted dc95 X1 full-flow controls and hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
