#!/usr/bin/env python3
"""Correlate exact-dc95 Draw/Dispatch preparation with X1 backend costs.

This is instrumentation-only. It does not skip, reorder, or alter guest GPU work.
It runs after the full-flow profiler/finalizer and attributes costs that happen on
Draw/Dispatch preparation threads to the originating command family.

Correlated signals:
  - staging upload bytes
  - buffer-copy calls/bytes
  - render-pass ends caused by OutsideOperation
  - upload/barrier count
  - Scheduler::Wait wall time

Heavy individual calls are emitted with a compact signature so a later A/B experiment
can target the expensive Draw/Dispatch shapes without another broad instrumentation pass.
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
        raise SystemExit("usage: transplant_dc95_draw_dispatch_correlation.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    # -------------------------------------------------------------------------
    # Profiler API and counters.
    # -------------------------------------------------------------------------
    header = vulkan / "vk_adreno_profiler.h"
    text = header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    enum class QcomEvent : u32 {\n        DescriptorTilerPolicy = 0,\n        DynamicStorageLimit,\n        ShaderProfile,\n        CustomBorderColor,\n        BorderColorSwizzle,\n        Count,\n    };\n''',
        '''    enum class QcomEvent : u32 {\n        DescriptorTilerPolicy = 0,\n        DynamicStorageLimit,\n        ShaderProfile,\n        CustomBorderColor,\n        BorderColorSwizzle,\n        Count,\n    };\n\n    enum class WorkOrigin : u8 {\n        None,\n        Draw,\n        Dispatch,\n    };\n''',
        "work-origin enum",
    )
    text = replace_once(
        text,
        '''    [[nodiscard]] bool DescriptorEnabled() const noexcept;\n\n    [[nodiscard]] u64 CurrentFrame() const noexcept {\n''',
        '''    [[nodiscard]] bool DescriptorEnabled() const noexcept;\n    [[nodiscard]] bool CorrelationEnabled() const noexcept;\n\n    void BeginWork(WorkOrigin origin);\n    void SetWorkSignature(u64 signature) noexcept;\n    void EndWork();\n\n    [[nodiscard]] u64 CurrentFrame() const noexcept {\n''',
        "work-origin API",
    )
    text = replace_once(
        text,
        '''        std::atomic<u64> barriers{0};\n\n        std::atomic<u64> present_waits{0};\n''',
        '''        std::atomic<u64> barriers{0};\n\n        std::atomic<u64> origin_draw_calls{0};\n        std::atomic<u64> origin_draw_upload_bytes{0};\n        std::atomic<u64> origin_draw_copy_calls{0};\n        std::atomic<u64> origin_draw_copy_bytes{0};\n        std::atomic<u64> origin_draw_outside_rp{0};\n        std::atomic<u64> origin_draw_barriers{0};\n        std::atomic<u64> origin_draw_wait_ns{0};\n        std::atomic<u64> origin_dispatch_calls{0};\n        std::atomic<u64> origin_dispatch_upload_bytes{0};\n        std::atomic<u64> origin_dispatch_copy_calls{0};\n        std::atomic<u64> origin_dispatch_copy_bytes{0};\n        std::atomic<u64> origin_dispatch_outside_rp{0};\n        std::atomic<u64> origin_dispatch_barriers{0};\n        std::atomic<u64> origin_dispatch_wait_ns{0};\n\n        std::atomic<u64> present_waits{0};\n''',
        "work-origin counters",
    )
    header.write_text(text, encoding="utf-8")

    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''u32 ThreadId() {\n    return static_cast<u32>(std::hash<std::thread::id>{}(std::this_thread::get_id()));\n}\n\n} // Anonymous namespace\n''',
        '''u32 ThreadId() {\n    return static_cast<u32>(std::hash<std::thread::id>{}(std::this_thread::get_id()));\n}\n\nstruct WorkCorrelationState {\n    AdrenoProfiler::WorkOrigin origin{AdrenoProfiler::WorkOrigin::None};\n    u64 signature{};\n    u64 upload_bytes{};\n    u64 copy_calls{};\n    u64 copy_bytes{};\n    u64 outside_rp{};\n    u64 barriers{};\n    u64 wait_ns{};\n};\n\nthread_local WorkCorrelationState work_correlation{};\n\nconst char* WorkOriginName(AdrenoProfiler::WorkOrigin origin) {\n    switch (origin) {\n    case AdrenoProfiler::WorkOrigin::Draw:\n        return "draw";\n    case AdrenoProfiler::WorkOrigin::Dispatch:\n        return "dispatch";\n    default:\n        return "none";\n    }\n}\n\n} // Anonymous namespace\n''',
        "thread-local work correlation state",
    )
    text = replace_once(
        text,
        '''bool AdrenoProfiler::DescriptorEnabled() const noexcept {\n    return qcom_driver.load(std::memory_order_relaxed) &&\n           Settings::values.x1_descriptor_ring_log.GetValue();\n}\n\nbool AdrenoProfiler::Enabled() const noexcept {\n''',
        '''bool AdrenoProfiler::DescriptorEnabled() const noexcept {\n    return qcom_driver.load(std::memory_order_relaxed) &&\n           Settings::values.x1_descriptor_ring_log.GetValue();\n}\n\nbool AdrenoProfiler::CorrelationEnabled() const noexcept {\n    return qcom_driver.load(std::memory_order_relaxed) &&\n           (Settings::values.x1_scheduler_sync_log.GetValue() ||\n            Settings::values.x1_upload_barrier_log.GetValue());\n}\n\nvoid AdrenoProfiler::BeginWork(WorkOrigin origin) {\n    if (!CorrelationEnabled() || origin == WorkOrigin::None) {\n        return;\n    }\n    // Draw/Dispatch scopes are not expected to nest. If a helper ever nests one,\n    // preserve the outer attribution rather than corrupting it.\n    if (work_correlation.origin != WorkOrigin::None) {\n        return;\n    }\n    work_correlation = WorkCorrelationState{};\n    work_correlation.origin = origin;\n}\n\nvoid AdrenoProfiler::SetWorkSignature(u64 signature) noexcept {\n    if (work_correlation.origin != WorkOrigin::None) {\n        work_correlation.signature = signature;\n    }\n}\n\nvoid AdrenoProfiler::EndWork() {\n    if (work_correlation.origin == WorkOrigin::None) {\n        return;\n    }\n    const WorkCorrelationState state = work_correlation;\n    work_correlation = WorkCorrelationState{};\n\n    auto add = [](std::atomic<u64>& dst, u64 value) {\n        dst.fetch_add(value, std::memory_order_relaxed);\n    };\n    if (state.origin == WorkOrigin::Draw) {\n        add(counters.origin_draw_calls, 1);\n        add(counters.origin_draw_upload_bytes, state.upload_bytes);\n        add(counters.origin_draw_copy_calls, state.copy_calls);\n        add(counters.origin_draw_copy_bytes, state.copy_bytes);\n        add(counters.origin_draw_outside_rp, state.outside_rp);\n        add(counters.origin_draw_barriers, state.barriers);\n        add(counters.origin_draw_wait_ns, state.wait_ns);\n    } else if (state.origin == WorkOrigin::Dispatch) {\n        add(counters.origin_dispatch_calls, 1);\n        add(counters.origin_dispatch_upload_bytes, state.upload_bytes);\n        add(counters.origin_dispatch_copy_calls, state.copy_calls);\n        add(counters.origin_dispatch_copy_bytes, state.copy_bytes);\n        add(counters.origin_dispatch_outside_rp, state.outside_rp);\n        add(counters.origin_dispatch_barriers, state.barriers);\n        add(counters.origin_dispatch_wait_ns, state.wait_ns);\n    }\n\n    constexpr u64 HEAVY_COPY_BYTES = 256ULL * 1024ULL;\n    const bool heavy = state.wait_ns >= slow_event_ns || state.copy_bytes >= HEAVY_COPY_BYTES ||\n                       state.outside_rp >= 2 || state.barriers >= 4;\n    if (heavy) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-FLOW][ORIGIN-CALL] frame={} thread={} kind={} sig=0x{:016X} "\n                 "upload={:.3f}MiB copy={} {:.3f}MiB outside={} barriers={} wait={:.3f}ms",\n                 CurrentFrame(), ThreadId(), WorkOriginName(state.origin), state.signature,\n                 ToMiB(state.upload_bytes), state.copy_calls, ToMiB(state.copy_bytes),\n                 state.outside_rp, state.barriers, ToMs(state.wait_ns));\n    }\n}\n\nbool AdrenoProfiler::Enabled() const noexcept {\n''',
        "work correlation lifecycle",
    )

    # Take the per-origin aggregate counters in the same reporting window.
    text = replace_once(
        text,
        '''    const u64 reordered_upload_bytes = Take(counters.reordered_upload_copy_bytes);\n    const u64 barriers = Take(counters.barriers);\n\n    const u64 present_waits = Take(counters.present_waits);\n''',
        '''    const u64 reordered_upload_bytes = Take(counters.reordered_upload_copy_bytes);\n    const u64 barriers = Take(counters.barriers);\n\n    const u64 origin_draw_calls = Take(counters.origin_draw_calls);\n    const u64 origin_draw_upload_bytes = Take(counters.origin_draw_upload_bytes);\n    const u64 origin_draw_copy_calls = Take(counters.origin_draw_copy_calls);\n    const u64 origin_draw_copy_bytes = Take(counters.origin_draw_copy_bytes);\n    const u64 origin_draw_outside_rp = Take(counters.origin_draw_outside_rp);\n    const u64 origin_draw_barriers = Take(counters.origin_draw_barriers);\n    const u64 origin_draw_wait_ns = Take(counters.origin_draw_wait_ns);\n    const u64 origin_dispatch_calls = Take(counters.origin_dispatch_calls);\n    const u64 origin_dispatch_upload_bytes = Take(counters.origin_dispatch_upload_bytes);\n    const u64 origin_dispatch_copy_calls = Take(counters.origin_dispatch_copy_calls);\n    const u64 origin_dispatch_copy_bytes = Take(counters.origin_dispatch_copy_bytes);\n    const u64 origin_dispatch_outside_rp = Take(counters.origin_dispatch_outside_rp);\n    const u64 origin_dispatch_barriers = Take(counters.origin_dispatch_barriers);\n    const u64 origin_dispatch_wait_ns = Take(counters.origin_dispatch_wait_ns);\n\n    const u64 present_waits = Take(counters.present_waits);\n''',
        "take work-origin counters",
    )
    text = replace_once(
        text,
        '''    if (QcomEnabled()) {\n        LOG_INFO(Render_Vulkan,\n''',
        '''    if (CorrelationEnabled()) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-FLOW][ORIGIN] frame={} frames={} "\n                 "draw={} upload={:.3f}MiB copy={} {:.3f}MiB outside={} barriers={} wait={:.3f}ms "\n                 "dispatch={} upload={:.3f}MiB copy={} {:.3f}MiB outside={} barriers={} wait={:.3f}ms",\n                 frame, frames, origin_draw_calls, ToMiB(origin_draw_upload_bytes),\n                 origin_draw_copy_calls, ToMiB(origin_draw_copy_bytes), origin_draw_outside_rp,\n                 origin_draw_barriers, ToMs(origin_draw_wait_ns), origin_dispatch_calls,\n                 ToMiB(origin_dispatch_upload_bytes), origin_dispatch_copy_calls,\n                 ToMiB(origin_dispatch_copy_bytes), origin_dispatch_outside_rp,\n                 origin_dispatch_barriers, ToMs(origin_dispatch_wait_ns));\n    }\n\n    if (QcomEnabled()) {\n        LOG_INFO(Render_Vulkan,\n''',
        "work-origin summary log",
    )

    # Attribute costs while a Draw/Dispatch preparation scope is active.
    text = replace_once(
        text,
        '''    case RenderPassEndReason::OutsideOperation:\n        counters.render_pass_end_outside_operation.fetch_add(1, std::memory_order_relaxed);\n        break;\n''',
        '''    case RenderPassEndReason::OutsideOperation:\n        counters.render_pass_end_outside_operation.fetch_add(1, std::memory_order_relaxed);\n        if (work_correlation.origin != WorkOrigin::None) {\n            ++work_correlation.outside_rp;\n        }\n        break;\n''',
        "outside-RP origin attribution",
    )
    text = replace_once(
        text,
        '''    } else {\n        counters.staging_upload_requests.fetch_add(1, std::memory_order_relaxed);\n        counters.staging_upload_bytes.fetch_add(bytes, std::memory_order_relaxed);\n    }\n}\n\nvoid AdrenoProfiler::RecordBufferCopy''',
        '''    } else {\n        counters.staging_upload_requests.fetch_add(1, std::memory_order_relaxed);\n        counters.staging_upload_bytes.fetch_add(bytes, std::memory_order_relaxed);\n        if (work_correlation.origin != WorkOrigin::None) {\n            work_correlation.upload_bytes += bytes;\n        }\n    }\n}\n\nvoid AdrenoProfiler::RecordBufferCopy''',
        "staging-upload origin attribution",
    )
    text = replace_once(
        text,
        '''    counters.buffer_copy_calls.fetch_add(1, std::memory_order_relaxed);\n    counters.buffer_copy_bytes.fetch_add(bytes, std::memory_order_relaxed);\n    if (reordered_upload) {\n''',
        '''    counters.buffer_copy_calls.fetch_add(1, std::memory_order_relaxed);\n    counters.buffer_copy_bytes.fetch_add(bytes, std::memory_order_relaxed);\n    if (work_correlation.origin != WorkOrigin::None) {\n        ++work_correlation.copy_calls;\n        work_correlation.copy_bytes += bytes;\n    }\n    if (reordered_upload) {\n''',
        "buffer-copy origin attribution",
    )
    text = replace_once(
        text,
        '''    if (forced_flush) {\n        counters.scheduler_forced_flushes.fetch_add(1, std::memory_order_relaxed);\n    }\n    LogSlow("SCHED", forced_flush ? "wait-forced-flush" : "wait", total, tick,\n''',
        '''    if (forced_flush) {\n        counters.scheduler_forced_flushes.fetch_add(1, std::memory_order_relaxed);\n    }\n    if (work_correlation.origin != WorkOrigin::None) {\n        work_correlation.wait_ns += total;\n    }\n    LogSlow("SCHED", forced_flush ? "wait-forced-flush" : "wait", total, tick,\n''',
        "scheduler-wait origin attribution",
    )
    text = replace_once(
        text,
        '''void AdrenoProfiler::RecordBarrier(const char*, u64 count) {\n    if (UploadEnabled()) {\n        counters.barriers.fetch_add(count, std::memory_order_relaxed);\n    }\n}\n''',
        '''void AdrenoProfiler::RecordBarrier(const char*, u64 count) {\n    if (UploadEnabled()) {\n        counters.barriers.fetch_add(count, std::memory_order_relaxed);\n        if (work_correlation.origin != WorkOrigin::None) {\n            work_correlation.barriers += count;\n        }\n    }\n}\n''',
        "barrier origin attribution",
    )
    cpp.write_text(text, encoding="utf-8")

    # -------------------------------------------------------------------------
    # Exact dc95 rasterizer scopes and compact command signatures.
    # -------------------------------------------------------------------------
    rasterizer = vulkan / "vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_buffer_cache.h"\n',
        '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n#include "video_core/renderer_vulkan/vk_buffer_cache.h"\n',
        "rasterizer profiler include",
    )
    text = replace_once(
        text,
        '''template <typename Func>\nvoid RasterizerVulkan::PrepareDraw(bool is_indexed, Func&& draw_func) {\n\n    SCOPE_EXIT {\n        gpu.TickWork();\n    };\n''',
        '''template <typename Func>\nvoid RasterizerVulkan::PrepareDraw(bool is_indexed, Func&& draw_func) {\n    auto& x1_origin_profiler = AdrenoProfiler::Get();\n    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Draw);\n    SCOPE_EXIT {\n        x1_origin_profiler.EndWork();\n        gpu.TickWork();\n    };\n''',
        "PrepareDraw origin scope",
    )
    text = replace_once(
        text,
        '''        const DrawParams draw_params{MakeDrawParams(draw_state, num_instances, is_indexed)};\n\n        scheduler.Record([draw_params](vk::CommandBuffer cmdbuf) {\n''',
        '''        const DrawParams draw_params{MakeDrawParams(draw_state, num_instances, is_indexed)};\n        const u64 draw_signature =\n            (static_cast<u64>(is_indexed) << 63) |\n            ((static_cast<u64>(draw_state.topology) & 0xFFULL) << 55) |\n            ((static_cast<u64>(draw_params.num_instances) & 0x7FFFFFULL) << 32) |\n            static_cast<u64>(draw_params.num_vertices);\n        AdrenoProfiler::Get().SetWorkSignature(draw_signature);\n\n        scheduler.Record([draw_params](vk::CommandBuffer cmdbuf) {\n''',
        "direct draw signature",
    )
    text = replace_once(
        text,
        '''    PrepareDraw(params.is_indexed, [this, &params] {\n        const auto indirect_buffer = buffer_cache.GetDrawIndirectBuffer();\n''',
        '''    PrepareDraw(params.is_indexed, [this, &params] {\n        const u64 draw_signature =\n            (1ULL << 62) | (static_cast<u64>(params.is_indexed) << 61) |\n            ((static_cast<u64>(params.max_draw_counts) & 0x1FFFFFFFULL) << 32) |\n            (static_cast<u64>(params.stride) & 0xFFFFFFFFULL);\n        AdrenoProfiler::Get().SetWorkSignature(draw_signature);\n        const auto indirect_buffer = buffer_cache.GetDrawIndirectBuffer();\n''',
        "indirect draw signature",
    )
    text = replace_once(
        text,
        '''void RasterizerVulkan::DrawTexture() {\n\n    SCOPE_EXIT {\n        gpu.TickWork();\n    };\n''',
        '''void RasterizerVulkan::DrawTexture() {\n    auto& x1_origin_profiler = AdrenoProfiler::Get();\n    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Draw);\n    x1_origin_profiler.SetWorkSignature(1ULL << 60);\n    SCOPE_EXIT {\n        x1_origin_profiler.EndWork();\n        gpu.TickWork();\n    };\n''',
        "DrawTexture origin scope",
    )
    text = replace_once(
        text,
        '''void RasterizerVulkan::DispatchCompute() {\n    FlushWork();\n''',
        '''void RasterizerVulkan::DispatchCompute() {\n    auto& x1_origin_profiler = AdrenoProfiler::Get();\n    x1_origin_profiler.BeginWork(AdrenoProfiler::WorkOrigin::Dispatch);\n    SCOPE_EXIT {\n        x1_origin_profiler.EndWork();\n    };\n    FlushWork();\n''',
        "DispatchCompute origin scope",
    )
    text = replace_once(
        text,
        '''    if (indirect_address) {\n        // DispatchIndirect\n''',
        '''    if (indirect_address) {\n        x1_origin_profiler.SetWorkSignature(\n            (1ULL << 63) | (static_cast<u64>(*indirect_address) & 0x7FFFFFFFFFFFFFFFULL));\n        // DispatchIndirect\n''',
        "indirect dispatch signature",
    )
    text = replace_once(
        text,
        '''    const std::array<u32, 3> dim{qmd.grid_dim_x, qmd.grid_dim_y, qmd.grid_dim_z};\n    const std::array<u32, 3> max_dim{device.GetMaxComputeWorkGroupCount()};\n''',
        '''    const std::array<u32, 3> dim{qmd.grid_dim_x, qmd.grid_dim_y, qmd.grid_dim_z};\n    const u64 dispatch_signature =\n        (static_cast<u64>(dim[0]) & 0x1FFFFFULL) |\n        ((static_cast<u64>(dim[1]) & 0x1FFFFFULL) << 21) |\n        ((static_cast<u64>(dim[2]) & 0x1FFFFFULL) << 42);\n    x1_origin_profiler.SetWorkSignature(dispatch_signature);\n    const std::array<u32, 3> max_dim{device.GetMaxComputeWorkGroupCount()};\n''',
        "direct dispatch signature",
    )
    rasterizer.write_text(text, encoding="utf-8")

    print("Transplanted exact dc95 Draw/Dispatch cost correlation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
