#!/usr/bin/env python3
'''Add observation-only X1 frame-build wall-time attribution on top of the diagnostic harness.

Expected order:
  - recreate the complete existing X1 diagnostic chain
  - transplant_dc95_diagnostic_harness.py
  - copy vk_x1_frame_build_profiler.h into the exact-dc95 Vulkan source tree
  - this pass

The new control is runtime-selectable and defaults OFF:
  X1 Log: Frame Build Attribution

The pass measures host steady-clock wall time only. It does not add waits, sleeps, submits,
flushes, fences, barriers, render-pass changes, swap changes, buffer-count changes, descriptor
policy changes, or guest-state changes.
'''

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def edit_section(text: str, start: str, end: str, editor, label: str) -> str:
    start_pos = text.find(start)
    if start_pos < 0:
        raise RuntimeError(f"{label}: start marker missing")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise RuntimeError(f"{label}: end marker missing")
    section = text[start_pos:end_pos]
    edited = editor(section)
    return text[:start_pos] + edited + text[end_pos:]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_frame_build_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"
    profiler_header = vulkan / "vk_x1_frame_build_profiler.h"
    if not profiler_header.exists():
        raise RuntimeError("vk_x1_frame_build_profiler.h must be copied before this pass")

    # -------------------------------------------------------------------------
    # Runtime setting + Qt checkbox.
    # -------------------------------------------------------------------------
    settings = root / "src/common/settings.h"
    text = settings.read_text(encoding="utf-8")
    anchor = '''    Setting<bool> x1_dequeue_attribution_log{
        linkage, false, "x1_dequeue_attribution_log", Category::Debugging};
'''
    replacement = anchor + '''    Setting<bool> x1_frame_build_attribution_log{
        linkage, false, "x1_frame_build_attribution_log", Category::Debugging};
'''
    text = replace_once(text, anchor, replacement, "frame-build setting")
    settings.write_text(text, encoding="utf-8")

    header = root / "src/yuzu/configuration/configure_debug.h"
    text = header.read_text(encoding="utf-8")
    anchor = '''    QCheckBox* x1_frame_cadence_log_checkbox{};
    QCheckBox* x1_dequeue_attribution_log_checkbox{};

    const Core::System& system;
'''
    replacement = '''    QCheckBox* x1_frame_cadence_log_checkbox{};
    QCheckBox* x1_dequeue_attribution_log_checkbox{};
    QCheckBox* x1_frame_build_attribution_log_checkbox{};

    const Core::System& system;
'''
    text = replace_once(text, anchor, replacement, "frame-build widget member")
    header.write_text(text, encoding="utf-8")

    cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = cpp.read_text(encoding="utf-8")

    anchor = '''    x1_dequeue_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Dequeue Attribution"), this);

'''
    replacement = anchor + '''    x1_frame_build_attribution_log_checkbox =
        new QCheckBox(tr("X1 Log: Frame Build Attribution"), this);

'''
    text = replace_once(text, anchor, replacement, "frame-build widget construction")

    anchor = '''    x1_dequeue_attribution_log_checkbox->setToolTip(
        tr("Log DequeueBuffer entry, free-slot selection time, return time, and the QueueBuffer "
           "records needed to split producer-frame latency. Disabled by default."));

'''
    replacement = anchor + '''    x1_frame_build_attribution_log_checkbox->setToolTip(
        tr("Measure CPU-side Vulkan frame-build wall time: Draw preparation, GraphicsPipeline "
           "Configure sub-stages, Dispatch, Clear and DrawTexture. Disabled by default."));

'''
    text = replace_once(text, anchor, replacement, "frame-build tooltip")

    anchor = '''    ui->gridLayout_1->addWidget(x1_frame_cadence_log_checkbox, 8, 0, 1, 2);
    ui->gridLayout_1->addWidget(x1_dequeue_attribution_log_checkbox, 8, 2, 1, 2);

'''
    replacement = anchor + '''    ui->gridLayout_1->addWidget(x1_frame_build_attribution_log_checkbox, 9, 0, 1, 2);

'''
    text = replace_once(text, anchor, replacement, "frame-build widget layout")

    anchor = '''    x1_dequeue_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_dequeue_attribution_log_checkbox->setChecked(
        Settings::values.x1_dequeue_attribution_log.GetValue());
'''
    replacement = anchor + '''    x1_frame_build_attribution_log_checkbox->setEnabled(runtime_lock);
    x1_frame_build_attribution_log_checkbox->setChecked(
        Settings::values.x1_frame_build_attribution_log.GetValue());
'''
    text = replace_once(text, anchor, replacement, "frame-build widget state")

    anchor = '''    Settings::values.x1_dequeue_attribution_log =
        x1_dequeue_attribution_log_checkbox->isChecked();
'''
    replacement = anchor + '''    Settings::values.x1_frame_build_attribution_log =
        x1_frame_build_attribution_log_checkbox->isChecked();
'''
    text = replace_once(text, anchor, replacement, "frame-build widget apply")

    anchor = '''    x1_frame_cadence_log_checkbox->setText(tr("X1 Log: Frame Cadence"));
    x1_dequeue_attribution_log_checkbox->setText(tr("X1 Log: Dequeue Attribution"));
}
'''
    replacement = '''    x1_frame_cadence_log_checkbox->setText(tr("X1 Log: Frame Cadence"));
    x1_dequeue_attribution_log_checkbox->setText(tr("X1 Log: Dequeue Attribution"));
    x1_frame_build_attribution_log_checkbox->setText(
        tr("X1 Log: Frame Build Attribution"));
}
'''
    text = replace_once(text, anchor, replacement, "frame-build widget retranslate")
    cpp.write_text(text, encoding="utf-8")

    # -------------------------------------------------------------------------
    # Rasterizer top-level frame-build timing.
    # -------------------------------------------------------------------------
    rasterizer = vulkan / "vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_x1_frame_build_profiler.h"\n',
        "frame-build profiler include",
    )

    text = replace_once(
        text,
        '''    scheduler.SetQueryCache(query_cache);
}
''',
        '''    scheduler.SetQueryCache(query_cache);
    X1FrameBuildProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
}
''',
        "frame-build profiler initialization",
    )

    prepare_anchor = '''template <typename Func>
void RasterizerVulkan::PrepareDraw(bool is_indexed, Func&& draw_func) {
    auto& x1_origin_profiler = AdrenoProfiler::Get();
    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Draw);
    SCOPE_EXIT {
        x1_origin_profiler.EndWork();
        gpu.TickWork();
    };
    FlushWork();
    gpu_memory->FlushCaching();

    GraphicsPipeline* const pipeline{pipeline_cache.CurrentGraphicsPipeline()};
    if (!pipeline) {
        return;
    }
    std::scoped_lock lock{buffer_cache.mutex, texture_cache.mutex};
    // update engine as channel may be different.
    pipeline->SetEngine(maxwell3d, gpu_memory);
    if (!pipeline->Configure(is_indexed))
        return;

    UpdateDynamicStates();

    query_cache.NotifySegment(true);
    HandleTransformFeedback();
    query_cache.CounterEnable(VideoCommon::QueryType::ZPassPixelCount64, maxwell3d->regs.zpass_pixel_count_enable);
    draw_func();
}
'''
    prepare_replacement = '''template <typename Func>
void RasterizerVulkan::PrepareDraw(bool is_indexed, Func&& draw_func) {
    auto& x1_origin_profiler = AdrenoProfiler::Get();
    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Draw);
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_draw_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    u64 x1_flush_ns{};
    u64 x1_memory_ns{};
    u64 x1_pre_config_ns{};
    u64 x1_configure_ns{};
    u64 x1_post_config_ns{};
    SCOPE_EXIT {
        if (x1_build_log) {
            x1_build_profiler.RecordPrepareDraw(
                X1FrameBuildProfiler::ElapsedNs(x1_draw_start), x1_flush_ns, x1_memory_ns,
                x1_pre_config_ns, x1_configure_ns, x1_post_config_ns);
        }
        x1_origin_profiler.EndWork();
        gpu.TickWork();
    };

    const auto x1_flush_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    FlushWork();
    if (x1_build_log) {
        x1_flush_ns = X1FrameBuildProfiler::ElapsedNs(x1_flush_start);
    }
    const auto x1_memory_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    gpu_memory->FlushCaching();
    if (x1_build_log) {
        x1_memory_ns = X1FrameBuildProfiler::ElapsedNs(x1_memory_start);
    }

    const auto x1_pre_config_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    GraphicsPipeline* const pipeline{pipeline_cache.CurrentGraphicsPipeline()};
    if (!pipeline) {
        if (x1_build_log) {
            x1_pre_config_ns = X1FrameBuildProfiler::ElapsedNs(x1_pre_config_start);
        }
        return;
    }
    std::scoped_lock lock{buffer_cache.mutex, texture_cache.mutex};
    // update engine as channel may be different.
    pipeline->SetEngine(maxwell3d, gpu_memory);
    if (x1_build_log) {
        x1_pre_config_ns = X1FrameBuildProfiler::ElapsedNs(x1_pre_config_start);
    }

    const auto x1_configure_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    if (!pipeline->Configure(is_indexed)) {
        if (x1_build_log) {
            x1_configure_ns = X1FrameBuildProfiler::ElapsedNs(x1_configure_start);
        }
        return;
    }
    if (x1_build_log) {
        x1_configure_ns = X1FrameBuildProfiler::ElapsedNs(x1_configure_start);
    }

    const auto x1_post_config_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    UpdateDynamicStates();

    query_cache.NotifySegment(true);
    HandleTransformFeedback();
    query_cache.CounterEnable(VideoCommon::QueryType::ZPassPixelCount64, maxwell3d->regs.zpass_pixel_count_enable);
    draw_func();
    if (x1_build_log) {
        x1_post_config_ns = X1FrameBuildProfiler::ElapsedNs(x1_post_config_start);
    }
}
'''
    text = replace_once(text, prepare_anchor, prepare_replacement, "PrepareDraw timing")

    def edit_draw_texture(section: str) -> str:
        anchor = '''void RasterizerVulkan::DrawTexture() {

'''
        replacement = '''void RasterizerVulkan::DrawTexture() {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    SCOPE_EXIT {
        if (x1_build_log) {
            x1_build_profiler.RecordDrawTexture(X1FrameBuildProfiler::ElapsedNs(x1_start));
        }
    };

'''
        return replace_once(section, anchor, replacement, "DrawTexture total timing")

    text = edit_section(
        text, "void RasterizerVulkan::DrawTexture() {", "void RasterizerVulkan::Clear(",
        edit_draw_texture, "DrawTexture section"
    )

    def edit_clear(section: str) -> str:
        anchor = '''void RasterizerVulkan::Clear(u32 layer_count) {
'''
        replacement = '''void RasterizerVulkan::Clear(u32 layer_count) {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    SCOPE_EXIT {
        if (x1_build_log) {
            x1_build_profiler.RecordClear(X1FrameBuildProfiler::ElapsedNs(x1_start));
        }
    };
'''
        return replace_once(section, anchor, replacement, "Clear total timing")

    text = edit_section(
        text, "void RasterizerVulkan::Clear(u32 layer_count) {", "void RasterizerVulkan::DispatchCompute() {",
        edit_clear, "Clear section"
    )

    def edit_dispatch(section: str) -> str:
        anchor = '''void RasterizerVulkan::DispatchCompute() {
'''
        replacement = '''void RasterizerVulkan::DispatchCompute() {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_dispatch_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    u64 x1_dispatch_flush_ns{};
    u64 x1_dispatch_memory_ns{};
    u64 x1_dispatch_configure_ns{};
    X1FrameBuildProfiler::TimePoint x1_dispatch_issue_start{};
    bool x1_dispatch_issue_started{};
    SCOPE_EXIT {
        if (x1_build_log) {
            const u64 x1_issue_ns = x1_dispatch_issue_started
                                        ? X1FrameBuildProfiler::ElapsedNs(x1_dispatch_issue_start)
                                        : 0;
            x1_build_profiler.RecordDispatch(
                X1FrameBuildProfiler::ElapsedNs(x1_dispatch_start), x1_dispatch_flush_ns,
                x1_dispatch_memory_ns, x1_dispatch_configure_ns, x1_issue_ns);
        }
    };
'''
        section = replace_once(section, anchor, replacement, "Dispatch total timing")
        section = replace_once(
            section,
            '''    FlushWork();
    gpu_memory->FlushCaching();
''',
            '''    const auto x1_flush_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    FlushWork();
    if (x1_build_log) {
        x1_dispatch_flush_ns = X1FrameBuildProfiler::ElapsedNs(x1_flush_start);
    }
    const auto x1_memory_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    gpu_memory->FlushCaching();
    if (x1_build_log) {
        x1_dispatch_memory_ns = X1FrameBuildProfiler::ElapsedNs(x1_memory_start);
    }
''',
            "Dispatch flush/memory timing",
        )
        configure_anchor = '''    std::scoped_lock lock{texture_cache.mutex, buffer_cache.mutex};
    if (!pipeline->Configure(*kepler_compute, *gpu_memory, scheduler, buffer_cache,
                             texture_cache)) {
        return;
    }

'''
        configure_replacement = '''    const auto x1_configure_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    std::scoped_lock lock{texture_cache.mutex, buffer_cache.mutex};
    if (!pipeline->Configure(*kepler_compute, *gpu_memory, scheduler, buffer_cache,
                             texture_cache)) {
        if (x1_build_log) {
            x1_dispatch_configure_ns = X1FrameBuildProfiler::ElapsedNs(x1_configure_start);
        }
        return;
    }
    if (x1_build_log) {
        x1_dispatch_configure_ns = X1FrameBuildProfiler::ElapsedNs(x1_configure_start);
        x1_dispatch_issue_start = X1FrameBuildProfiler::Now();
        x1_dispatch_issue_started = true;
    }

'''
        section = replace_once(
            section, configure_anchor, configure_replacement, "Dispatch configure timing"
        )
        return section

    text = edit_section(
        text, "void RasterizerVulkan::DispatchCompute() {", "void RasterizerVulkan::ResetCounter(",
        edit_dispatch, "Dispatch section"
    )

    def edit_flush_commands(section: str) -> str:
        anchor = '''void RasterizerVulkan::FlushCommands() {
'''
        replacement = '''void RasterizerVulkan::FlushCommands() {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    SCOPE_EXIT {
        if (x1_build_log) {
            x1_build_profiler.RecordFlushCommands(X1FrameBuildProfiler::ElapsedNs(x1_start));
        }
    };
'''
        return replace_once(section, anchor, replacement, "FlushCommands timing")

    text = edit_section(
        text, "void RasterizerVulkan::FlushCommands() {", "void RasterizerVulkan::TickFrame() {",
        edit_flush_commands, "FlushCommands section"
    )

    tick_anchor = '''void RasterizerVulkan::TickFrame() {
    draw_counter = 0;
'''
    tick_replacement = '''void RasterizerVulkan::TickFrame() {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_tick_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    draw_counter = 0;
'''
    text = replace_once(text, tick_anchor, tick_replacement, "TickFrame timing start")

    tick_end_anchor = '''    {
        std::scoped_lock lock{buffer_cache.mutex};
        buffer_cache.TickFrame();
    }
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    tick_end_replacement = '''    {
        std::scoped_lock lock{buffer_cache.mutex};
        buffer_cache.TickFrame();
    }
    if (x1_build_log) {
        x1_build_profiler.RecordTickFrame(X1FrameBuildProfiler::ElapsedNs(x1_tick_start));
    }
    x1_build_profiler.FrameEnd();
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    text = replace_once(text, tick_end_anchor, tick_end_replacement, "TickFrame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    # -------------------------------------------------------------------------
    # GraphicsPipeline::ConfigureImpl sub-stage timing.
    # -------------------------------------------------------------------------
    graphics = vulkan / "vk_graphics_pipeline.cpp"
    text = graphics.read_text(encoding="utf-8")
    if '#include "common/scope_exit.h"\n' not in text:
        text = replace_once(
            text,
            '#include "common/settings.h"\n',
            '#include "common/settings.h"\n#include "common/scope_exit.h"\n',
            "graphics scope-exit include",
        )
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_graphics_pipeline.h"\n',
        '#include "video_core/renderer_vulkan/vk_graphics_pipeline.h"\n'
        '#include "video_core/renderer_vulkan/vk_x1_frame_build_profiler.h"\n',
        "graphics frame-build profiler include",
    )

    cfg_prefix = '''template <typename Spec>
bool GraphicsPipeline::ConfigureImpl(bool is_indexed) {
    boost::container::small_vector<VideoCommon::ImageViewInOut, 64> views;
'''
    cfg_replacement = '''template <typename Spec>
bool GraphicsPipeline::ConfigureImpl(bool is_indexed) {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_cfg_total_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    u64 x1_sync_desc_ns{};
    u64 x1_stage_scan_ns{};
    u64 x1_fill_views_ns{};
    u64 x1_bind_views_ns{};
    u64 x1_update_buffers_ns{};
    u64 x1_descriptor_prepare_ns{};
    u64 x1_configure_draw_ns{};
    SCOPE_EXIT {
        if (x1_build_log) {
            x1_build_profiler.RecordGraphicsConfigure(
                X1FrameBuildProfiler::ElapsedNs(x1_cfg_total_start), x1_sync_desc_ns,
                x1_stage_scan_ns, x1_fill_views_ns, x1_bind_views_ns, x1_update_buffers_ns,
                x1_descriptor_prepare_ns, x1_configure_draw_ns);
        }
    };

    boost::container::small_vector<VideoCommon::ImageViewInOut, 64> views;
'''
    text = replace_once(text, cfg_prefix, cfg_replacement, "ConfigureImpl timing state")

    text = replace_once(
        text,
        '''    texture_cache.SynchronizeDescriptors(false);

    buffer_cache.SetUniformBuffersState(enabled_uniform_buffer_masks, &uniform_buffer_sizes);
''',
        '''    const auto x1_sync_desc_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    texture_cache.SynchronizeDescriptors(false);
    if (x1_build_log) {
        x1_sync_desc_ns = X1FrameBuildProfiler::ElapsedNs(x1_sync_desc_start);
    }

    const auto x1_stage_scan_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    buffer_cache.SetUniformBuffersState(enabled_uniform_buffer_masks, &uniform_buffer_sizes);
''',
        "Configure descriptor sync/stage start",
    )

    text = replace_once(
        text,
        '''    ASSERT(views.size() == num_image_elements);
    ASSERT(samplers.size() == num_textures);
    texture_cache.FillImageViews(std::span(views.data(), views.size()), false, Spec::has_images);

    VideoCommon::ImageViewInOut* texture_buffer_it{views.data()};
''',
        '''    if (x1_build_log) {
        x1_stage_scan_ns = X1FrameBuildProfiler::ElapsedNs(x1_stage_scan_start);
    }
    ASSERT(views.size() == num_image_elements);
    ASSERT(samplers.size() == num_textures);
    const auto x1_fill_views_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    texture_cache.FillImageViews(std::span(views.data(), views.size()), false, Spec::has_images);
    if (x1_build_log) {
        x1_fill_views_ns = X1FrameBuildProfiler::ElapsedNs(x1_fill_views_start);
    }

    const auto x1_bind_views_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    VideoCommon::ImageViewInOut* texture_buffer_it{views.data()};
''',
        "Configure stage/fill/bind transition",
    )

    text = replace_once(
        text,
        '''    if (regs.transform_feedback_enabled != 0) {
        scheduler.RequestOutsideRenderPassOperationContext();
    }

    buffer_cache.UpdateGraphicsBuffers(is_indexed);
    buffer_cache.BindHostGeometryBuffers(is_indexed);

    guest_descriptor_queue.Acquire(scheduler, num_descriptor_entries, uses_descriptor_buffer);
''',
        '''    if (x1_build_log) {
        x1_bind_views_ns = X1FrameBuildProfiler::ElapsedNs(x1_bind_views_start);
    }
    const auto x1_update_buffers_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    if (regs.transform_feedback_enabled != 0) {
        scheduler.RequestOutsideRenderPassOperationContext();
    }

    buffer_cache.UpdateGraphicsBuffers(is_indexed);
    buffer_cache.BindHostGeometryBuffers(is_indexed);
    if (x1_build_log) {
        x1_update_buffers_ns = X1FrameBuildProfiler::ElapsedNs(x1_update_buffers_start);
    }

    const auto x1_descriptor_prepare_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    guest_descriptor_queue.Acquire(scheduler, num_descriptor_entries, uses_descriptor_buffer);
''',
        "Configure bind/update/descriptor transition",
    )

    tail_anchor = '''    texture_cache.UpdateRenderTargets(false);
    texture_cache.CheckFeedbackLoop(std::span<const VideoCommon::ImageViewInOut>{views.data(),
                                                                                 views.size()});
    if (IsBuilt() && !pipeline) {
        return false;
    }
    return ConfigureDraw(rescaling, render_area);
}
'''
    tail_replacement = '''    texture_cache.UpdateRenderTargets(false);
    texture_cache.CheckFeedbackLoop(std::span<const VideoCommon::ImageViewInOut>{views.data(),
                                                                                 views.size()});
    if (x1_build_log) {
        x1_descriptor_prepare_ns = X1FrameBuildProfiler::ElapsedNs(x1_descriptor_prepare_start);
    }
    if (IsBuilt() && !pipeline) {
        return false;
    }
    const auto x1_configure_draw_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    const bool x1_configure_result = ConfigureDraw(rescaling, render_area);
    if (x1_build_log) {
        x1_configure_draw_ns = X1FrameBuildProfiler::ElapsedNs(x1_configure_draw_start);
    }
    return x1_configure_result;
}
'''
    text = replace_once(text, tail_anchor, tail_replacement, "Configure descriptor/configure-draw tail")
    graphics.write_text(text, encoding="utf-8")

    # Static behavior guard: the attribution pass must not introduce timing/render policy verbs.
    for path in (rasterizer, graphics):
        final = path.read_text(encoding="utf-8")
        if "x1_frame_build_attribution_log" not in settings.read_text(encoding="utf-8"):
            raise RuntimeError("frame-build setting disappeared")
        if "X1FrameBuildProfiler" not in final:
            raise RuntimeError(f"frame-build profiler hook missing from {path.name}")

    print("Transplanted exact dc95 X1 frame-build attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
