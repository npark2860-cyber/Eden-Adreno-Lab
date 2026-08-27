#!/usr/bin/env python3
'''Add observation-only X1 frame-build wall-time attribution on top of the final harness chain.

Expected order:
  - recreate the complete existing X1 diagnostic chain
  - transplant_dc95_diagnostic_harness.py
  - copy vk_x1_frame_build_profiler.h into the exact-dc95 Vulkan source tree
  - this pass

The new control is runtime-selectable and defaults OFF:
  X1 Log: Frame Build Attribution

Important: this pass intentionally anchors to the FINAL generated source after the existing
Draw/Dispatch correlation, Draw-other reason, texture, alias, Uniform, cadence and harness passes.
It preserves those scopes and adds steady-clock timing around them.

No wait, sleep, submit, flush, fence, barrier, render-pass, swap interval, buffer count,
descriptor policy, guest-state, or scheduling policy is added or changed by this pass.
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

    ui_header = root / "src/yuzu/configuration/configure_debug.h"
    text = ui_header.read_text(encoding="utf-8")
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
    ui_header.write_text(text, encoding="utf-8")

    ui_cpp = root / "src/yuzu/configuration/configure_debug.cpp"
    text = ui_cpp.read_text(encoding="utf-8")
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
    ui_cpp.write_text(text, encoding="utf-8")

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

    def edit_prepare_draw(section: str) -> str:
        # Preserve the existing origin/correlation lifecycle and all nested reason scopes.
        prefix = '''    auto& x1_origin_profiler = AdrenoProfiler::Get();
    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Draw);
'''
        prefix_replacement = prefix + '''    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_draw_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    u64 x1_flush_ns{};
    u64 x1_memory_ns{};
    u64 x1_pre_config_ns{};
    u64 x1_configure_ns{};
    u64 x1_post_config_ns{};
'''
        section = replace_once(section, prefix, prefix_replacement, "PrepareDraw timing state")

        scope = '''    SCOPE_EXIT {
        x1_origin_profiler.EndWork();
        gpu.TickWork();
    };
'''
        scope_replacement = '''    SCOPE_EXIT {
        if (x1_build_log) {
            x1_build_profiler.RecordPrepareDraw(
                X1FrameBuildProfiler::ElapsedNs(x1_draw_start), x1_flush_ns, x1_memory_ns,
                x1_pre_config_ns, x1_configure_ns, x1_post_config_ns);
        }
        x1_origin_profiler.EndWork();
        gpu.TickWork();
    };
'''
        section = replace_once(section, scope, scope_replacement, "PrepareDraw timing scope")

        flush_block = '''    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherFlushWork);
    FlushWork();
    x1_origin_profiler.EndBufferCategory();
'''
        flush_replacement = '''    const auto x1_flush_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherFlushWork);
    FlushWork();
    x1_origin_profiler.EndBufferCategory();
    if (x1_build_log) {
        x1_flush_ns = X1FrameBuildProfiler::ElapsedNs(x1_flush_start);
    }
'''
        section = replace_once(section, flush_block, flush_replacement, "PrepareDraw FlushWork timing")

        memory_block = '''    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherFlushCaching);
    gpu_memory->FlushCaching();
    x1_origin_profiler.EndBufferCategory();

    GraphicsPipeline* const pipeline{pipeline_cache.CurrentGraphicsPipeline()};
'''
        memory_replacement = '''    const auto x1_memory_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherFlushCaching);
    gpu_memory->FlushCaching();
    x1_origin_profiler.EndBufferCategory();
    if (x1_build_log) {
        x1_memory_ns = X1FrameBuildProfiler::ElapsedNs(x1_memory_start);
    }

    const auto x1_pre_config_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    GraphicsPipeline* const pipeline{pipeline_cache.CurrentGraphicsPipeline()};
'''
        section = replace_once(section, memory_block, memory_replacement, "PrepareDraw memory/pre-config start")

        pipeline_missing = '''    if (!pipeline) {
        return;
    }
'''
        pipeline_missing_replacement = '''    if (!pipeline) {
        if (x1_build_log) {
            x1_pre_config_ns = X1FrameBuildProfiler::ElapsedNs(x1_pre_config_start);
        }
        return;
    }
'''
        section = replace_once(
            section, pipeline_missing, pipeline_missing_replacement, "PrepareDraw missing pipeline timing"
        )

        set_engine = '''    pipeline->SetEngine(maxwell3d, gpu_memory);
    if (!pipeline->Configure(is_indexed))
        return;
'''
        set_engine_replacement = '''    pipeline->SetEngine(maxwell3d, gpu_memory);
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
'''
        section = replace_once(section, set_engine, set_engine_replacement, "PrepareDraw Configure timing")

        post_start = '''    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherDynamicStates);
'''
        post_start_replacement = '''    const auto x1_post_config_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherDynamicStates);
'''
        section = replace_once(section, post_start, post_start_replacement, "PrepareDraw post-config start")

        post_end = '''    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherDrawCommand);
    draw_func();
    x1_origin_profiler.EndBufferCategory();
'''
        post_end_replacement = post_end + '''    if (x1_build_log) {
        x1_post_config_ns = X1FrameBuildProfiler::ElapsedNs(x1_post_config_start);
    }
'''
        section = replace_once(section, post_end, post_end_replacement, "PrepareDraw post-config end")
        return section

    text = edit_section(
        text,
        "template <typename Func>\nvoid RasterizerVulkan::PrepareDraw(",
        "void RasterizerVulkan::Draw(bool is_indexed",
        edit_prepare_draw,
        "PrepareDraw section",
    )

    def add_total_scope(section: str, signature: str, record_call: str, label: str) -> str:
        anchor = signature + "\n"
        replacement = anchor + '''    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_build_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    SCOPE_EXIT {
        if (x1_build_log) {
            ''' + record_call + '''(X1FrameBuildProfiler::ElapsedNs(x1_build_start));
        }
    };
'''
        return replace_once(section, anchor, replacement, label)

    text = edit_section(
        text,
        "void RasterizerVulkan::DrawTexture() {",
        "void RasterizerVulkan::Clear(",
        lambda section: add_total_scope(
            section,
            "void RasterizerVulkan::DrawTexture() {",
            "x1_build_profiler.RecordDrawTexture",
            "DrawTexture total timing",
        ),
        "DrawTexture section",
    )

    text = edit_section(
        text,
        "void RasterizerVulkan::Clear(u32 layer_count) {",
        "void RasterizerVulkan::DispatchCompute() {",
        lambda section: add_total_scope(
            section,
            "void RasterizerVulkan::Clear(u32 layer_count) {",
            "x1_build_profiler.RecordClear",
            "Clear total timing",
        ),
        "Clear section",
    )

    def edit_dispatch(section: str) -> str:
        # Total timing starts before the diagnostic A/B gate; baseline runs keep all A/B controls OFF.
        anchor = '''void RasterizerVulkan::DispatchCompute() {
'''
        replacement = anchor + '''    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
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

        flush_memory = '''    FlushWork();
    gpu_memory->FlushCaching();

    ComputePipeline* const pipeline{pipeline_cache.CurrentComputePipeline()};
'''
        flush_memory_replacement = '''    const auto x1_dispatch_flush_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    FlushWork();
    if (x1_build_log) {
        x1_dispatch_flush_ns = X1FrameBuildProfiler::ElapsedNs(x1_dispatch_flush_start);
    }
    const auto x1_dispatch_memory_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    gpu_memory->FlushCaching();
    if (x1_build_log) {
        x1_dispatch_memory_ns = X1FrameBuildProfiler::ElapsedNs(x1_dispatch_memory_start);
    }

    ComputePipeline* const pipeline{pipeline_cache.CurrentComputePipeline()};
'''
        section = replace_once(section, flush_memory, flush_memory_replacement, "Dispatch flush/memory timing")

        configure = '''    std::scoped_lock lock{texture_cache.mutex, buffer_cache.mutex};
    if (!pipeline->Configure(*kepler_compute, *gpu_memory, scheduler, buffer_cache,
                             texture_cache)) {
        return;
    }

'''
        configure_replacement = '''    const auto x1_dispatch_configure_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    std::scoped_lock lock{texture_cache.mutex, buffer_cache.mutex};
    if (!pipeline->Configure(*kepler_compute, *gpu_memory, scheduler, buffer_cache,
                             texture_cache)) {
        if (x1_build_log) {
            x1_dispatch_configure_ns =
                X1FrameBuildProfiler::ElapsedNs(x1_dispatch_configure_start);
        }
        return;
    }
    if (x1_build_log) {
        x1_dispatch_configure_ns = X1FrameBuildProfiler::ElapsedNs(x1_dispatch_configure_start);
        x1_dispatch_issue_start = X1FrameBuildProfiler::Now();
        x1_dispatch_issue_started = true;
    }

'''
        section = replace_once(section, configure, configure_replacement, "Dispatch configure timing")
        return section

    text = edit_section(
        text,
        "void RasterizerVulkan::DispatchCompute() {",
        "void RasterizerVulkan::ResetCounter(",
        edit_dispatch,
        "Dispatch section",
    )

    text = edit_section(
        text,
        "void RasterizerVulkan::FlushCommands() {",
        "void RasterizerVulkan::TickFrame() {",
        lambda section: add_total_scope(
            section,
            "void RasterizerVulkan::FlushCommands() {",
            "x1_build_profiler.RecordFlushCommands",
            "FlushCommands timing",
        ),
        "FlushCommands section",
    )

    tick_prefix = '''void RasterizerVulkan::TickFrame() {
    draw_counter = 0;
'''
    tick_replacement = '''void RasterizerVulkan::TickFrame() {
    auto& x1_build_profiler = X1FrameBuildProfiler::Get();
    const bool x1_build_log = x1_build_profiler.Enabled();
    const auto x1_tick_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    draw_counter = 0;
'''
    text = replace_once(text, tick_prefix, tick_replacement, "TickFrame timing start")

    tick_tail = '''    {
        std::scoped_lock lock{buffer_cache.mutex};
        buffer_cache.TickFrame();
    }
}

bool RasterizerVulkan::AccelerateConditionalRendering() {
'''
    tick_tail_replacement = '''    {
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
    text = replace_once(text, tick_tail, tick_tail_replacement, "TickFrame report hook")
    rasterizer.write_text(text, encoding="utf-8")

    # -------------------------------------------------------------------------
    # GraphicsPipeline::ConfigureImpl sub-stage timing.
    # Preserve all existing Draw-other category wrappers.
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

    sync_block = '''    auto& x1_other_profiler = AdrenoProfiler::Get();
    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherTextureSyncDescriptors);
    texture_cache.SynchronizeDescriptors(false);
    x1_other_profiler.EndBufferCategory();

    buffer_cache.SetUniformBuffersState(enabled_uniform_buffer_masks, &uniform_buffer_sizes);
'''
    sync_replacement = '''    auto& x1_other_profiler = AdrenoProfiler::Get();
    const auto x1_sync_desc_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherTextureSyncDescriptors);
    texture_cache.SynchronizeDescriptors(false);
    x1_other_profiler.EndBufferCategory();
    if (x1_build_log) {
        x1_sync_desc_ns = X1FrameBuildProfiler::ElapsedNs(x1_sync_desc_start);
    }

    const auto x1_stage_scan_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    buffer_cache.SetUniformBuffersState(enabled_uniform_buffer_masks, &uniform_buffer_sizes);
'''
    text = replace_once(text, sync_block, sync_replacement, "Configure descriptor sync/stage start")

    fill_block = '''    ASSERT(views.size() == num_image_elements);
    ASSERT(samplers.size() == num_textures);
    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherTextureFillImageViews);
    texture_cache.FillImageViews(std::span(views.data(), views.size()), false, Spec::has_images);
    x1_other_profiler.EndBufferCategory();

    VideoCommon::ImageViewInOut* texture_buffer_it{views.data()};
'''
    fill_replacement = '''    if (x1_build_log) {
        x1_stage_scan_ns = X1FrameBuildProfiler::ElapsedNs(x1_stage_scan_start);
    }
    ASSERT(views.size() == num_image_elements);
    ASSERT(samplers.size() == num_textures);
    const auto x1_fill_views_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherTextureFillImageViews);
    texture_cache.FillImageViews(std::span(views.data(), views.size()), false, Spec::has_images);
    x1_other_profiler.EndBufferCategory();
    if (x1_build_log) {
        x1_fill_views_ns = X1FrameBuildProfiler::ElapsedNs(x1_fill_views_start);
    }

    const auto x1_bind_views_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    VideoCommon::ImageViewInOut* texture_buffer_it{views.data()};
'''
    text = replace_once(text, fill_block, fill_replacement, "Configure stage/fill/bind transition")

    update_start = '''    if (regs.transform_feedback_enabled != 0) {
        x1_other_profiler.BeginBufferCategory(
            AdrenoProfiler::BufferCategory::OtherTransformFeedbackBreak);
'''
    update_start_replacement = '''    if (x1_build_log) {
        x1_bind_views_ns = X1FrameBuildProfiler::ElapsedNs(x1_bind_views_start);
    }
    const auto x1_update_buffers_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    if (regs.transform_feedback_enabled != 0) {
        x1_other_profiler.BeginBufferCategory(
            AdrenoProfiler::BufferCategory::OtherTransformFeedbackBreak);
'''
    text = replace_once(text, update_start, update_start_replacement, "Configure bind/update transition")

    descriptor_acquire = '''    buffer_cache.UpdateGraphicsBuffers(is_indexed);
    buffer_cache.BindHostGeometryBuffers(is_indexed);

    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherDescriptorAcquire);
'''
    descriptor_acquire_replacement = '''    buffer_cache.UpdateGraphicsBuffers(is_indexed);
    buffer_cache.BindHostGeometryBuffers(is_indexed);
    if (x1_build_log) {
        x1_update_buffers_ns = X1FrameBuildProfiler::ElapsedNs(x1_update_buffers_start);
    }

    const auto x1_descriptor_prepare_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherDescriptorAcquire);
'''
    text = replace_once(
        text, descriptor_acquire, descriptor_acquire_replacement, "Configure update/descriptor transition"
    )

    feedback_tail = '''    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherFeedbackLoop);
    texture_cache.CheckFeedbackLoop(std::span<const VideoCommon::ImageViewInOut>{views.data(),
                                                                                 views.size()});
    x1_other_profiler.EndBufferCategory();
    if (IsBuilt() && !pipeline) {
        return false;
    }
    x1_other_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherConfigureDraw);
    const bool x1_configure_draw_result = ConfigureDraw(rescaling, render_area);
    x1_other_profiler.EndBufferCategory();
    return x1_configure_draw_result;
}
'''
    feedback_tail_replacement = '''    x1_other_profiler.BeginBufferCategory(
        AdrenoProfiler::BufferCategory::OtherFeedbackLoop);
    texture_cache.CheckFeedbackLoop(std::span<const VideoCommon::ImageViewInOut>{views.data(),
                                                                                 views.size()});
    x1_other_profiler.EndBufferCategory();
    if (x1_build_log) {
        x1_descriptor_prepare_ns = X1FrameBuildProfiler::ElapsedNs(x1_descriptor_prepare_start);
    }
    if (IsBuilt() && !pipeline) {
        return false;
    }
    const auto x1_configure_draw_start =
        x1_build_log ? X1FrameBuildProfiler::Now() : X1FrameBuildProfiler::TimePoint{};
    x1_other_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherConfigureDraw);
    const bool x1_configure_draw_result = ConfigureDraw(rescaling, render_area);
    x1_other_profiler.EndBufferCategory();
    if (x1_build_log) {
        x1_configure_draw_ns = X1FrameBuildProfiler::ElapsedNs(x1_configure_draw_start);
    }
    return x1_configure_draw_result;
}
'''
    text = replace_once(
        text, feedback_tail, feedback_tail_replacement, "Configure descriptor/configure-draw tail"
    )
    graphics.write_text(text, encoding="utf-8")

    # -------------------------------------------------------------------------
    # Static sanity markers. Workflow performs the stronger unchanged-file hash checks.
    # -------------------------------------------------------------------------
    final_settings = settings.read_text(encoding="utf-8")
    final_rasterizer = rasterizer.read_text(encoding="utf-8")
    final_graphics = graphics.read_text(encoding="utf-8")
    for marker in (
        "x1_frame_build_attribution_log",
        "x1_frame_cadence_log",
        "x1_dequeue_attribution_log",
    ):
        if marker not in final_settings:
            raise RuntimeError(f"required setting missing after pass: {marker}")
    for marker in (
        "RecordPrepareDraw",
        "RecordDispatch",
        "RecordDrawTexture",
        "RecordClear",
        "OtherFlushWork",
        "OtherDrawCommand",
    ):
        if marker not in final_rasterizer:
            raise RuntimeError(f"required rasterizer marker missing after pass: {marker}")
    for marker in (
        "RecordGraphicsConfigure",
        "OtherTextureSyncDescriptors",
        "OtherTextureFillImageViews",
        "OtherDescriptorAcquire",
        "OtherConfigureDraw",
    ):
        if marker not in final_graphics:
            raise RuntimeError(f"required graphics marker missing after pass: {marker}")

    print("Transplanted exact dc95 X1 frame-build attribution over final diagnostic harness chain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
