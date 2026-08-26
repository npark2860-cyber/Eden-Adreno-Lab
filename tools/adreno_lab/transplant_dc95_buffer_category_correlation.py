#!/usr/bin/env python3
"""Split exact-dc95 Draw/Dispatch BufferCache costs by resource category.

Expected order:
  - full-flow profiler/finalizer
  - Draw/Dispatch correlation transplant
  - Draw/Dispatch A/B controls

This pass is instrumentation-only. It does not skip, reorder, cache, or alter guest work.
It attributes existing X1-FLOW upload/copy/RP-break/barrier signals to:
  other / index / vertex / uniform / storage / texture-buffer / transform-feedback / indirect

The generic BufferCache stays backend-neutral: Vulkan BufferCacheParams exposes two optional
hooks, and buffer_cache.h calls them only when the parameter type provides them.
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
        raise SystemExit("usage: transplant_dc95_buffer_category_correlation.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # ------------------------------------------------------------------
    # Profiler public API.
    # ------------------------------------------------------------------
    header = vulkan / "vk_adreno_profiler.h"
    text = header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    enum class WorkOrigin : u8 {\n        None,\n        Draw,\n        Dispatch,\n    };\n''',
        '''    enum class WorkOrigin : u8 {\n        None,\n        Draw,\n        Dispatch,\n    };\n\n    enum class BufferCategory : u8 {\n        None = 0,\n        Other,\n        Index,\n        Vertex,\n        Uniform,\n        Storage,\n        TextureBuffer,\n        TransformFeedback,\n        Indirect,\n        Count,\n    };\n''',
        "buffer-category enum",
    )
    text = replace_once(
        text,
        '''    void BeginWork(WorkOrigin origin);\n    void SetWorkSignature(u64 signature) noexcept;\n    void EndWork();\n''',
        '''    void BeginWork(WorkOrigin origin);\n    void SetWorkSignature(u64 signature) noexcept;\n    void EndWork();\n\n    void BeginBufferCategory(BufferCategory category) noexcept;\n    void EndBufferCategory() noexcept;\n''',
        "buffer-category API",
    )
    header.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Profiler thread-local category and aggregate matrix.
    # ------------------------------------------------------------------
    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''thread_local WorkCorrelationState work_correlation{};\n\nconst char* WorkOriginName''',
        '''thread_local WorkCorrelationState work_correlation{};\n\nstruct BufferCategoryState {\n    AdrenoProfiler::BufferCategory category{AdrenoProfiler::BufferCategory::None};\n    u32 depth{};\n};\n\nstruct BufferCategoryAggregate {\n    std::atomic<u64> scopes{0};\n    std::atomic<u64> upload_requests{0};\n    std::atomic<u64> upload_bytes{0};\n    std::atomic<u64> copy_calls{0};\n    std::atomic<u64> copy_bytes{0};\n    std::atomic<u64> outside_rp{0};\n    std::atomic<u64> barriers{0};\n    std::atomic<u64> wait_ns{0};\n};\n\nthread_local BufferCategoryState buffer_category_state{};\nconstexpr size_t BUFFER_CATEGORY_COUNT =\n    static_cast<size_t>(AdrenoProfiler::BufferCategory::Count);\nstd::array<BufferCategoryAggregate, BUFFER_CATEGORY_COUNT> draw_buffer_categories{};\nstd::array<BufferCategoryAggregate, BUFFER_CATEGORY_COUNT> dispatch_buffer_categories{};\n\nAdrenoProfiler::BufferCategory EffectiveBufferCategory() {\n    return buffer_category_state.category == AdrenoProfiler::BufferCategory::None\n               ? AdrenoProfiler::BufferCategory::Other\n               : buffer_category_state.category;\n}\n\nBufferCategoryAggregate* ActiveBufferAggregate() {\n    if (work_correlation.origin == AdrenoProfiler::WorkOrigin::None) {\n        return nullptr;\n    }\n    const size_t index = static_cast<size_t>(EffectiveBufferCategory());\n    if (work_correlation.origin == AdrenoProfiler::WorkOrigin::Draw) {\n        return &draw_buffer_categories[index];\n    }\n    return &dispatch_buffer_categories[index];\n}\n\nconst char* BufferCategoryName(AdrenoProfiler::BufferCategory category) {\n    switch (category) {\n    case AdrenoProfiler::BufferCategory::Other:\n        return "other";\n    case AdrenoProfiler::BufferCategory::Index:\n        return "index";\n    case AdrenoProfiler::BufferCategory::Vertex:\n        return "vertex";\n    case AdrenoProfiler::BufferCategory::Uniform:\n        return "uniform";\n    case AdrenoProfiler::BufferCategory::Storage:\n        return "storage";\n    case AdrenoProfiler::BufferCategory::TextureBuffer:\n        return "texture-buffer";\n    case AdrenoProfiler::BufferCategory::TransformFeedback:\n        return "transform-feedback";\n    case AdrenoProfiler::BufferCategory::Indirect:\n        return "indirect";\n    default:\n        return "none";\n    }\n}\n\nvoid BufferAddUpload(u64 bytes) {\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->upload_requests.fetch_add(1, std::memory_order_relaxed);\n        aggregate->upload_bytes.fetch_add(bytes, std::memory_order_relaxed);\n    }\n}\n\nvoid BufferAddCopy(u64 bytes) {\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->copy_calls.fetch_add(1, std::memory_order_relaxed);\n        aggregate->copy_bytes.fetch_add(bytes, std::memory_order_relaxed);\n    }\n}\n\nvoid BufferAddOutsideRp() {\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->outside_rp.fetch_add(1, std::memory_order_relaxed);\n    }\n}\n\nvoid BufferAddBarrier(u64 count) {\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->barriers.fetch_add(count, std::memory_order_relaxed);\n    }\n}\n\nvoid BufferAddWait(u64 nanoseconds) {\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);\n    }\n}\n\nvoid ReportBufferCategoryGroup(\n    const char* kind, std::array<BufferCategoryAggregate, BUFFER_CATEGORY_COUNT>& categories,\n    u64 frame, u64 frames) {\n    for (size_t index = 1; index < BUFFER_CATEGORY_COUNT; ++index) {\n        auto& aggregate = categories[index];\n        const u64 scopes = Take(aggregate.scopes);\n        const u64 upload_requests = Take(aggregate.upload_requests);\n        const u64 upload_bytes = Take(aggregate.upload_bytes);\n        const u64 copy_calls = Take(aggregate.copy_calls);\n        const u64 copy_bytes = Take(aggregate.copy_bytes);\n        const u64 outside_rp = Take(aggregate.outside_rp);\n        const u64 barriers = Take(aggregate.barriers);\n        const u64 wait_ns = Take(aggregate.wait_ns);\n        if (scopes == 0 && upload_requests == 0 && copy_calls == 0 && outside_rp == 0 &&\n            barriers == 0 && wait_ns == 0) {\n            continue;\n        }\n        const auto category = static_cast<AdrenoProfiler::BufferCategory>(index);\n        LOG_INFO(Render_Vulkan,\n                 "[X1-FLOW][BUFFER] frame={} frames={} kind={} cat={} scopes={} "\n                 "uploadReq={} upload={:.3f}MiB copy={} {:.3f}MiB outside={} barriers={} "\n                 "wait={:.3f}ms",\n                 frame, frames, kind, BufferCategoryName(category), scopes, upload_requests,\n                 ToMiB(upload_bytes), copy_calls, ToMiB(copy_bytes), outside_rp, barriers,\n                 ToMs(wait_ns));\n    }\n}\n\nvoid ReportBufferCategories(u64 frame, u64 frames) {\n    ReportBufferCategoryGroup("draw", draw_buffer_categories, frame, frames);\n    ReportBufferCategoryGroup("dispatch", dispatch_buffer_categories, frame, frames);\n}\n\nconst char* WorkOriginName''',
        "buffer-category state",
    )

    text = replace_once(
        text,
        '''void AdrenoProfiler::SetWorkSignature(u64 signature) noexcept {\n    if (work_correlation.origin != WorkOrigin::None) {\n        work_correlation.signature = signature;\n    }\n}\n\nvoid AdrenoProfiler::EndWork()''',
        '''void AdrenoProfiler::SetWorkSignature(u64 signature) noexcept {\n    if (work_correlation.origin != WorkOrigin::None) {\n        work_correlation.signature = signature;\n    }\n}\n\nvoid AdrenoProfiler::BeginBufferCategory(BufferCategory category) noexcept {\n    if (!CorrelationEnabled() || work_correlation.origin == WorkOrigin::None ||\n        category == BufferCategory::None) {\n        return;\n    }\n    if (buffer_category_state.depth != 0) {\n        ++buffer_category_state.depth;\n        return;\n    }\n    buffer_category_state.category = category;\n    buffer_category_state.depth = 1;\n    if (auto* aggregate = ActiveBufferAggregate()) {\n        aggregate->scopes.fetch_add(1, std::memory_order_relaxed);\n    }\n}\n\nvoid AdrenoProfiler::EndBufferCategory() noexcept {\n    if (buffer_category_state.depth == 0) {\n        return;\n    }\n    if (--buffer_category_state.depth == 0) {\n        buffer_category_state.category = BufferCategory::None;\n    }\n}\n\nvoid AdrenoProfiler::EndWork()''',
        "buffer-category lifecycle",
    )

    # Existing Draw/Dispatch attribution points gain a second, finer bucket.
    text = replace_once(
        text,
        '''        if (work_correlation.origin != WorkOrigin::None) {\n            ++work_correlation.outside_rp;\n        }\n        break;\n''',
        '''        if (work_correlation.origin != WorkOrigin::None) {\n            ++work_correlation.outside_rp;\n            BufferAddOutsideRp();\n        }\n        break;\n''',
        "category outside-rp attribution",
    )
    text = replace_once(
        text,
        '''        if (work_correlation.origin != WorkOrigin::None) {\n            work_correlation.upload_bytes += bytes;\n        }\n    }\n}\n\nvoid AdrenoProfiler::RecordBufferCopy''',
        '''        if (work_correlation.origin != WorkOrigin::None) {\n            work_correlation.upload_bytes += bytes;\n            BufferAddUpload(bytes);\n        }\n    }\n}\n\nvoid AdrenoProfiler::RecordBufferCopy''',
        "category upload attribution",
    )
    text = replace_once(
        text,
        '''    if (work_correlation.origin != WorkOrigin::None) {\n        ++work_correlation.copy_calls;\n        work_correlation.copy_bytes += bytes;\n    }\n    if (reordered_upload) {\n''',
        '''    if (work_correlation.origin != WorkOrigin::None) {\n        ++work_correlation.copy_calls;\n        work_correlation.copy_bytes += bytes;\n        BufferAddCopy(bytes);\n    }\n    if (reordered_upload) {\n''',
        "category copy attribution",
    )
    text = replace_once(
        text,
        '''    if (work_correlation.origin != WorkOrigin::None) {\n        work_correlation.wait_ns += total;\n    }\n    LogSlow("SCHED", forced_flush ? "wait-forced-flush" : "wait", total, tick,\n''',
        '''    if (work_correlation.origin != WorkOrigin::None) {\n        work_correlation.wait_ns += total;\n        BufferAddWait(total);\n    }\n    LogSlow("SCHED", forced_flush ? "wait-forced-flush" : "wait", total, tick,\n''',
        "category wait attribution",
    )
    text = replace_once(
        text,
        '''        if (work_correlation.origin != WorkOrigin::None) {\n            work_correlation.barriers += count;\n        }\n    }\n}\n''',
        '''        if (work_correlation.origin != WorkOrigin::None) {\n            work_correlation.barriers += count;\n            BufferAddBarrier(count);\n        }\n    }\n}\n''',
        "category barrier attribution",
    )
    text = replace_once(
        text,
        '''    if (QcomEnabled()) {\n        LOG_INFO(Render_Vulkan,\n''',
        '''    if (CorrelationEnabled()) {\n        ReportBufferCategories(frame, frames);\n    }\n\n    if (QcomEnabled()) {\n        LOG_INFO(Render_Vulkan,\n''',
        "buffer-category frame report",
    )
    cpp.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Vulkan BufferCacheParams bridge; no Vulkan include in generic cache.
    # ------------------------------------------------------------------
    vk_header = vulkan / "vk_buffer_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_compute_pass.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n'
        '#include "video_core/renderer_vulkan/vk_compute_pass.h"\n',
        "vk buffer profiler include",
    )
    text = replace_once(
        text,
        '''struct BufferCacheParams {\n    using Runtime = Vulkan::BufferCacheRuntime;\n''',
        '''struct BufferCacheParams {\n    using Runtime = Vulkan::BufferCacheRuntime;\n'''
        '''\n    static void BeginX1BufferCategory(u32 category) {\n        AdrenoProfiler::Get().BeginBufferCategory(\n            static_cast<AdrenoProfiler::BufferCategory>(category));\n    }\n\n    static void EndX1BufferCategory() {\n        AdrenoProfiler::Get().EndBufferCategory();\n    }\n''',
        "vk BufferCacheParams bridge",
    )
    vk_header.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Generic BufferCache scopes. Calls are compile-time optional via requires.
    # Numeric values match AdrenoProfiler::BufferCategory above.
    # ------------------------------------------------------------------
    cache = root / "src/video_core/buffer_cache/buffer_cache.h"
    text = cache.read_text(encoding="utf-8")

    geometry_old = '''template <class P>\nvoid BufferCache<P>::BindHostGeometryBuffers(bool is_indexed) {\n    if (is_indexed) {\n        BindHostIndexBuffer();\n    } else if constexpr (!HAS_FULL_INDEX_AND_PRIMITIVE_SUPPORT) {\n        const auto& draw_state = maxwell3d->draw_manager.draw_state;\n        if (draw_state.topology == Maxwell::PrimitiveTopology::Quads ||\n            draw_state.topology == Maxwell::PrimitiveTopology::QuadStrip) {\n            runtime.BindQuadIndexBuffer(draw_state.topology, draw_state.vertex_buffer.first,\n                                        draw_state.vertex_buffer.count);\n        }\n    }\n    BindHostVertexBuffers();\n    BindHostTransformFeedbackBuffers();\n    if (current_draw_indirect) {\n        BindHostDrawIndirectBuffers();\n    }\n}\n'''
    geometry_new = '''template <class P>\nvoid BufferCache<P>::BindHostGeometryBuffers(bool is_indexed) {\n    const auto x1_category = [&](u32 category, auto&& func) {\n        if constexpr (requires { P::BeginX1BufferCategory(category); P::EndX1BufferCategory(); }) {\n            P::BeginX1BufferCategory(category);\n            func();\n            P::EndX1BufferCategory();\n        } else {\n            func();\n        }\n    };\n    if (is_indexed) {\n        x1_category(2, [&] { BindHostIndexBuffer(); });\n    } else if constexpr (!HAS_FULL_INDEX_AND_PRIMITIVE_SUPPORT) {\n        const auto& draw_state = maxwell3d->draw_manager.draw_state;\n        if (draw_state.topology == Maxwell::PrimitiveTopology::Quads ||\n            draw_state.topology == Maxwell::PrimitiveTopology::QuadStrip) {\n            x1_category(2, [&] {\n                runtime.BindQuadIndexBuffer(draw_state.topology, draw_state.vertex_buffer.first,\n                                            draw_state.vertex_buffer.count);\n            });\n        }\n    }\n    x1_category(3, [&] { BindHostVertexBuffers(); });\n    x1_category(7, [&] { BindHostTransformFeedbackBuffers(); });\n    if (current_draw_indirect) {\n        x1_category(8, [&] { BindHostDrawIndirectBuffers(); });\n    }\n}\n'''
    text = replace_once(text, geometry_old, geometry_new, "geometry category scopes")

    stage_old = '''template <class P>\nvoid BufferCache<P>::BindHostStageBuffers(size_t stage) {\n    BindHostGraphicsUniformBuffers(stage);\n    BindHostGraphicsStorageBuffers(stage);\n    BindHostGraphicsTextureBuffers(stage);\n}\n'''
    stage_new = '''template <class P>\nvoid BufferCache<P>::BindHostStageBuffers(size_t stage) {\n    const auto x1_category = [&](u32 category, auto&& func) {\n        if constexpr (requires { P::BeginX1BufferCategory(category); P::EndX1BufferCategory(); }) {\n            P::BeginX1BufferCategory(category);\n            func();\n            P::EndX1BufferCategory();\n        } else {\n            func();\n        }\n    };\n    x1_category(4, [&] { BindHostGraphicsUniformBuffers(stage); });\n    x1_category(5, [&] { BindHostGraphicsStorageBuffers(stage); });\n    x1_category(6, [&] { BindHostGraphicsTextureBuffers(stage); });\n}\n'''
    text = replace_once(text, stage_old, stage_new, "graphics stage category scopes")

    compute_bind_old = '''template <class P>\nvoid BufferCache<P>::BindHostComputeBuffers() {\n    BindHostComputeUniformBuffers();\n    BindHostComputeStorageBuffers();\n    BindHostComputeTextureBuffers();\n    if (any_buffer_uploaded) {\n        runtime.PostCopyBarrier();\n        any_buffer_uploaded = false;\n    }\n}\n'''
    compute_bind_new = '''template <class P>\nvoid BufferCache<P>::BindHostComputeBuffers() {\n    const auto x1_category = [&](u32 category, auto&& func) {\n        if constexpr (requires { P::BeginX1BufferCategory(category); P::EndX1BufferCategory(); }) {\n            P::BeginX1BufferCategory(category);\n            func();\n            P::EndX1BufferCategory();\n        } else {\n            func();\n        }\n    };\n    x1_category(4, [&] { BindHostComputeUniformBuffers(); });\n    x1_category(5, [&] { BindHostComputeStorageBuffers(); });\n    x1_category(6, [&] { BindHostComputeTextureBuffers(); });\n    if (any_buffer_uploaded) {\n        runtime.PostCopyBarrier();\n        any_buffer_uploaded = false;\n    }\n}\n'''
    text = replace_once(text, compute_bind_old, compute_bind_new, "compute bind category scopes")

    update_graphics_old = '''template <class P>\nvoid BufferCache<P>::DoUpdateGraphicsBuffers(bool is_indexed) {\n    BufferOperations([&]() {\n        if (is_indexed) {\n            UpdateIndexBuffer();\n        }\n        UpdateVertexBuffers();\n        UpdateTransformFeedbackBuffers();\n        for (size_t stage = 0; stage < NUM_STAGES; ++stage) {\n            UpdateUniformBuffers(stage);\n            UpdateStorageBuffers(stage);\n            UpdateTextureBuffers(stage);\n        }\n        if (current_draw_indirect) {\n            UpdateDrawIndirect();\n        }\n    });\n}\n'''
    update_graphics_new = '''template <class P>\nvoid BufferCache<P>::DoUpdateGraphicsBuffers(bool is_indexed) {\n    const auto x1_category = [&](u32 category, auto&& func) {\n        if constexpr (requires { P::BeginX1BufferCategory(category); P::EndX1BufferCategory(); }) {\n            P::BeginX1BufferCategory(category);\n            func();\n            P::EndX1BufferCategory();\n        } else {\n            func();\n        }\n    };\n    BufferOperations([&]() {\n        if (is_indexed) {\n            x1_category(2, [&] { UpdateIndexBuffer(); });\n        }\n        x1_category(3, [&] { UpdateVertexBuffers(); });\n        x1_category(7, [&] { UpdateTransformFeedbackBuffers(); });\n        for (size_t stage = 0; stage < NUM_STAGES; ++stage) {\n            x1_category(4, [&] { UpdateUniformBuffers(stage); });\n            x1_category(5, [&] { UpdateStorageBuffers(stage); });\n            x1_category(6, [&] { UpdateTextureBuffers(stage); });\n        }\n        if (current_draw_indirect) {\n            x1_category(8, [&] { UpdateDrawIndirect(); });\n        }\n    });\n}\n'''
    text = replace_once(text, update_graphics_old, update_graphics_new, "graphics update category scopes")

    update_compute_old = '''template <class P>\nvoid BufferCache<P>::DoUpdateComputeBuffers() {\n    BufferOperations([&]() {\n        UpdateComputeUniformBuffers();\n        UpdateComputeStorageBuffers();\n        UpdateComputeTextureBuffers();\n    });\n}\n'''
    update_compute_new = '''template <class P>\nvoid BufferCache<P>::DoUpdateComputeBuffers() {\n    const auto x1_category = [&](u32 category, auto&& func) {\n        if constexpr (requires { P::BeginX1BufferCategory(category); P::EndX1BufferCategory(); }) {\n            P::BeginX1BufferCategory(category);\n            func();\n            P::EndX1BufferCategory();\n        } else {\n            func();\n        }\n    };\n    BufferOperations([&]() {\n        x1_category(4, [&] { UpdateComputeUniformBuffers(); });\n        x1_category(5, [&] { UpdateComputeStorageBuffers(); });\n        x1_category(6, [&] { UpdateComputeTextureBuffers(); });\n    });\n}\n'''
    text = replace_once(text, update_compute_old, update_compute_new, "compute update category scopes")
    cache.write_text(text, encoding="utf-8")

    print("Applied exact-dc95 X1 buffer-category correlation instrumentation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
