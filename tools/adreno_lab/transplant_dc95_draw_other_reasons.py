#!/usr/bin/env python3
"Instrument exact-dc95 Draw category=other with concrete reason buckets."

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_draw_other_reasons.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # Extend the existing BufferCategory enum without changing numeric values 1..8.
    header = vulkan / "vk_adreno_profiler.h"
    text = header.read_text(encoding="utf-8")
    old = '''        TransformFeedback,\n        Indirect,\n        Count,\n'''
    new = '''        TransformFeedback,\n        Indirect,\n        OtherTextureSyncDescriptors,\n        OtherTextureFillImageViews,\n        OtherTransformFeedbackBreak,\n        OtherDescriptorAcquire,\n        OtherPostCopyBarrier,\n        OtherUpdateRenderTargets,\n        OtherFeedbackLoop,\n        OtherConfigureDraw,\n        OtherFlushWork,\n        OtherFlushCaching,\n        OtherDynamicStates,\n        OtherQuerySegment,\n        OtherTransformFeedback,\n        OtherQueryCounter,\n        OtherDrawCommand,\n        Count,\n'''
    text = replace_once(text, old, new, "draw-other reason categories")
    header.write_text(text, encoding="utf-8")

    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")
    old = '''    case AdrenoProfiler::BufferCategory::Indirect:\n        return "indirect";\n    default:\n'''
    new = '''    case AdrenoProfiler::BufferCategory::Indirect:\n        return "indirect";\n    case AdrenoProfiler::BufferCategory::OtherTextureSyncDescriptors:\n        return "other/texture-sync-descriptors";\n    case AdrenoProfiler::BufferCategory::OtherTextureFillImageViews:\n        return "other/texture-fill-image-views";\n    case AdrenoProfiler::BufferCategory::OtherTransformFeedbackBreak:\n        return "other/transform-feedback-break";\n    case AdrenoProfiler::BufferCategory::OtherDescriptorAcquire:\n        return "other/descriptor-acquire";\n    case AdrenoProfiler::BufferCategory::OtherPostCopyBarrier:\n        return "other/post-copy-barrier";\n    case AdrenoProfiler::BufferCategory::OtherUpdateRenderTargets:\n        return "other/update-render-targets";\n    case AdrenoProfiler::BufferCategory::OtherFeedbackLoop:\n        return "other/feedback-loop";\n    case AdrenoProfiler::BufferCategory::OtherConfigureDraw:\n        return "other/configure-draw";\n    case AdrenoProfiler::BufferCategory::OtherFlushWork:\n        return "other/flush-work";\n    case AdrenoProfiler::BufferCategory::OtherFlushCaching:\n        return "other/flush-caching";\n    case AdrenoProfiler::BufferCategory::OtherDynamicStates:\n        return "other/dynamic-states";\n    case AdrenoProfiler::BufferCategory::OtherQuerySegment:\n        return "other/query-segment";\n    case AdrenoProfiler::BufferCategory::OtherTransformFeedback:\n        return "other/transform-feedback";\n    case AdrenoProfiler::BufferCategory::OtherQueryCounter:\n        return "other/query-counter";\n    case AdrenoProfiler::BufferCategory::OtherDrawCommand:\n        return "other/draw-command";\n    default:\n'''
    text = replace_once(text, old, new, "draw-other category names")
    cpp.write_text(text, encoding="utf-8")

    graphics = vulkan / "vk_graphics_pipeline.cpp"
    text = graphics.read_text(encoding="utf-8")

    old = '''    texture_cache.SynchronizeDescriptors(false);\n\n    buffer_cache.SetUniformBuffersState(enabled_uniform_buffer_masks, &uniform_buffer_sizes);\n'''
    new = '''    auto& x1_other_profiler = AdrenoProfiler::Get();\n    x1_other_profiler.BeginBufferCategory(\n        AdrenoProfiler::BufferCategory::OtherTextureSyncDescriptors);\n    texture_cache.SynchronizeDescriptors(false);\n    x1_other_profiler.EndBufferCategory();\n\n    buffer_cache.SetUniformBuffersState(enabled_uniform_buffer_masks, &uniform_buffer_sizes);\n'''
    text = replace_once(text, old, new, "texture sync reason")

    old = '''    texture_cache.FillImageViews(std::span(views.data(), views.size()), false, Spec::has_images);\n\n    VideoCommon::ImageViewInOut* texture_buffer_it{views.data()};\n'''
    new = '''    x1_other_profiler.BeginBufferCategory(\n        AdrenoProfiler::BufferCategory::OtherTextureFillImageViews);\n    texture_cache.FillImageViews(std::span(views.data(), views.size()), false, Spec::has_images);\n    x1_other_profiler.EndBufferCategory();\n\n    VideoCommon::ImageViewInOut* texture_buffer_it{views.data()};\n'''
    text = replace_once(text, old, new, "fill image views reason")

    old = '''    if (regs.transform_feedback_enabled != 0) {\n        scheduler.RequestOutsideRenderPassOperationContext();\n    }\n\n    buffer_cache.UpdateGraphicsBuffers(is_indexed);\n'''
    new = '''    if (regs.transform_feedback_enabled != 0) {\n        x1_other_profiler.BeginBufferCategory(\n            AdrenoProfiler::BufferCategory::OtherTransformFeedbackBreak);\n        scheduler.RequestOutsideRenderPassOperationContext();\n        x1_other_profiler.EndBufferCategory();\n    }\n\n    buffer_cache.UpdateGraphicsBuffers(is_indexed);\n'''
    text = replace_once(text, old, new, "transform feedback break reason")

    old = '''    guest_descriptor_queue.Acquire(scheduler, num_descriptor_entries, uses_descriptor_buffer);\n\n    RescalingPushConstant rescaling;\n'''
    new = '''    x1_other_profiler.BeginBufferCategory(\n        AdrenoProfiler::BufferCategory::OtherDescriptorAcquire);\n    guest_descriptor_queue.Acquire(scheduler, num_descriptor_entries, uses_descriptor_buffer);\n    x1_other_profiler.EndBufferCategory();\n\n    RescalingPushConstant rescaling;\n'''
    text = replace_once(text, old, new, "descriptor acquire reason")

    old = '''    if (buffer_cache.any_buffer_uploaded) {\n        buffer_cache.runtime.PostCopyBarrier();\n        buffer_cache.any_buffer_uploaded = false;\n    }\n    texture_cache.UpdateRenderTargets(false);\n    texture_cache.CheckFeedbackLoop(std::span<const VideoCommon::ImageViewInOut>{views.data(),\n                                                                                 views.size()});\n'''
    new = '''    if (buffer_cache.any_buffer_uploaded) {\n        x1_other_profiler.BeginBufferCategory(\n            AdrenoProfiler::BufferCategory::OtherPostCopyBarrier);\n        buffer_cache.runtime.PostCopyBarrier();\n        x1_other_profiler.EndBufferCategory();\n        buffer_cache.any_buffer_uploaded = false;\n    }\n    x1_other_profiler.BeginBufferCategory(\n        AdrenoProfiler::BufferCategory::OtherUpdateRenderTargets);\n    texture_cache.UpdateRenderTargets(false);\n    x1_other_profiler.EndBufferCategory();\n    x1_other_profiler.BeginBufferCategory(\n        AdrenoProfiler::BufferCategory::OtherFeedbackLoop);\n    texture_cache.CheckFeedbackLoop(std::span<const VideoCommon::ImageViewInOut>{views.data(),\n                                                                                 views.size()});\n    x1_other_profiler.EndBufferCategory();\n'''
    text = replace_once(text, old, new, "post-copy/RT/feedback reasons")

    old = '''    return ConfigureDraw(rescaling, render_area);\n}\n'''
    new = '''    x1_other_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherConfigureDraw);\n    const bool x1_configure_draw_result = ConfigureDraw(rescaling, render_area);\n    x1_other_profiler.EndBufferCategory();\n    return x1_configure_draw_result;\n}\n'''
    text = replace_once(text, old, new, "configure draw reason")
    graphics.write_text(text, encoding="utf-8")

    rasterizer = vulkan / "vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")

    old = '''    FlushWork();\n    gpu_memory->FlushCaching();\n\n    GraphicsPipeline* const pipeline{pipeline_cache.CurrentGraphicsPipeline()};\n'''
    new = '''    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherFlushWork);\n    FlushWork();\n    x1_origin_profiler.EndBufferCategory();\n    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherFlushCaching);\n    gpu_memory->FlushCaching();\n    x1_origin_profiler.EndBufferCategory();\n\n    GraphicsPipeline* const pipeline{pipeline_cache.CurrentGraphicsPipeline()};\n'''
    text = replace_once(text, old, new, "prepare draw flush reasons")

    old = '''    UpdateDynamicStates();\n\n    query_cache.NotifySegment(true);\n    HandleTransformFeedback();\n    query_cache.CounterEnable(VideoCommon::QueryType::ZPassPixelCount64, maxwell3d->regs.zpass_pixel_count_enable);\n    draw_func();\n'''
    new = '''    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherDynamicStates);\n    UpdateDynamicStates();\n    x1_origin_profiler.EndBufferCategory();\n\n    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherQuerySegment);\n    query_cache.NotifySegment(true);\n    x1_origin_profiler.EndBufferCategory();\n    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherTransformFeedback);\n    HandleTransformFeedback();\n    x1_origin_profiler.EndBufferCategory();\n    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherQueryCounter);\n    query_cache.CounterEnable(VideoCommon::QueryType::ZPassPixelCount64,\n                              maxwell3d->regs.zpass_pixel_count_enable);\n    x1_origin_profiler.EndBufferCategory();\n    x1_origin_profiler.BeginBufferCategory(AdrenoProfiler::BufferCategory::OtherDrawCommand);\n    draw_func();\n    x1_origin_profiler.EndBufferCategory();\n'''
    text = replace_once(text, old, new, "prepare draw outer reasons")
    rasterizer.write_text(text, encoding="utf-8")

    print("Applied Draw/other reason buckets to exact-dc95 generated source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
