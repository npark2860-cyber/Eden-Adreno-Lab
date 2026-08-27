#!/usr/bin/env python3
'''Add passive telemetry for exact-dc95 graphics Uniform path selection and fast-stream reuse.

Expected order:
  - transplant_dc95_alias_sync_redundancy.py
  - this pass

Instrumentation-only. It does not skip, cache, batch, reorder, or change any Uniform upload,
binding, dirty tracking, barrier, render-pass, or scheduler behavior. The fast-key tracker is
fixed-size and is rotated at the existing profiler report boundary.
'''

from pathlib import Path
import subprocess
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_uniform_stream_reuse.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    profiler_h = vulkan / "vk_adreno_profiler.h"
    if "RecordX1AliasSyncCopy" not in profiler_h.read_text(encoding="utf-8"):
        parent = Path(__file__).with_name("transplant_dc95_alias_sync_redundancy.py")
        subprocess.run([sys.executable, str(parent), str(root)], check=True)

    text = profiler_h.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    void RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id, u64 texture_frame,\n                               u64 source_modification_tick, u32 region_count,\n                               u64 region_signature) noexcept;\n''',
        '''    void RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id, u64 texture_frame,\n                               u64 source_modification_tick, u32 region_count,\n                               u64 region_signature) noexcept;\n    void RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size, bool fast,\n                             bool alignment_stream, bool cached_clean,\n                             bool skip_policy_active) noexcept;\n''',
        "uniform profiler API",
    )

    text = replace_once(
        text,
        '''        std::atomic<u64> alias_sync_copies{0};\n''',
        '''        std::atomic<u64> uniform_visits{0};\n        std::atomic<u64> uniform_bytes{0};\n        std::atomic<u64> uniform_fast{0};\n        std::atomic<u64> uniform_fast_bytes{0};\n        std::atomic<u64> uniform_fast_alignment{0};\n        std::atomic<u64> uniform_fast_skip{0};\n        std::atomic<u64> uniform_cached{0};\n        std::atomic<u64> uniform_cached_bytes{0};\n        std::atomic<u64> uniform_cached_clean{0};\n        std::atomic<u64> uniform_cached_upload{0};\n        std::atomic<u64> uniform_skip_policy_visits{0};\n        std::atomic<u64> uniform_fast_unique_keys{0};\n        std::atomic<u64> uniform_fast_repeat_key{0};\n        std::atomic<u64> uniform_fast_same_frame{0};\n        std::atomic<u64> uniform_fast_same_draw{0};\n        std::atomic<u64> uniform_fast_consecutive_frame{0};\n        std::atomic<u64> uniform_fast_table_overflow{0};\n\n        std::atomic<u64> alias_sync_copies{0};\n''',
        "uniform aggregate counters",
    )

    text = replace_once(
        text,
        '''    std::array<X1AliasSyncPairState, X1_ALIAS_SYNC_PAIR_CAPACITY> alias_sync_pairs{};\n\n    const u32 report_every_frames;\n''',
        '''    std::array<X1AliasSyncPairState, X1_ALIAS_SYNC_PAIR_CAPACITY> alias_sync_pairs{};\n\n    static constexpr size_t X1_UNIFORM_FAST_KEY_CAPACITY = 16384;\n    static constexpr size_t X1_UNIFORM_FAST_PROBE_LIMIT = 32;\n\n    struct X1UniformFastKeyState {\n        std::atomic_flag lock = ATOMIC_FLAG_INIT;\n        bool occupied{};\n        u32 stage{};\n        u32 index{};\n        u32 size{};\n        u64 device_addr{};\n        u64 last_frame{};\n        u64 last_draw_serial{};\n    };\n\n    std::array<X1UniformFastKeyState, X1_UNIFORM_FAST_KEY_CAPACITY> uniform_fast_keys{};\n\n    const u32 report_every_frames;\n''',
        "bounded uniform fast-key table",
    )
    profiler_h.write_text(text, encoding="utf-8")

    profiler_cpp = vulkan / "vk_adreno_profiler.cpp"
    text = profiler_cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''void AdrenoProfiler::RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id,\n''',
        '''void AdrenoProfiler::RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size,\n                                             bool fast, bool alignment_stream, bool cached_clean,\n                                             bool skip_policy_active) noexcept {\n    if (!CorrelationEnabled()) {\n        return;\n    }\n\n    counters.uniform_visits.fetch_add(1, std::memory_order_relaxed);\n    counters.uniform_bytes.fetch_add(size, std::memory_order_relaxed);\n    if (skip_policy_active) {\n        counters.uniform_skip_policy_visits.fetch_add(1, std::memory_order_relaxed);\n    }\n\n    if (!fast) {\n        counters.uniform_cached.fetch_add(1, std::memory_order_relaxed);\n        counters.uniform_cached_bytes.fetch_add(size, std::memory_order_relaxed);\n        if (cached_clean) {\n            counters.uniform_cached_clean.fetch_add(1, std::memory_order_relaxed);\n        } else {\n            counters.uniform_cached_upload.fetch_add(1, std::memory_order_relaxed);\n        }\n        return;\n    }\n\n    counters.uniform_fast.fetch_add(1, std::memory_order_relaxed);\n    counters.uniform_fast_bytes.fetch_add(size, std::memory_order_relaxed);\n    if (alignment_stream) {\n        counters.uniform_fast_alignment.fetch_add(1, std::memory_order_relaxed);\n    } else {\n        counters.uniform_fast_skip.fetch_add(1, std::memory_order_relaxed);\n    }\n\n    u64 hash = device_addr;\n    hash ^= static_cast<u64>(stage) << 56;\n    hash ^= static_cast<u64>(index) << 48;\n    hash ^= static_cast<u64>(size) << 16;\n    hash ^= hash >> 33;\n    hash *= 0xff51afd7ed558ccdULL;\n    hash ^= hash >> 33;\n    hash *= 0xc4ceb9fe1a85ec53ULL;\n    hash ^= hash >> 33;\n    const size_t start = static_cast<size_t>(hash) & (X1_UNIFORM_FAST_KEY_CAPACITY - 1);\n    const u64 frame = CurrentFrame();\n    const u64 draw_serial = work_correlation.origin == WorkOrigin::Draw ? work_correlation.serial : 0;\n\n    for (size_t probe = 0; probe < X1_UNIFORM_FAST_PROBE_LIMIT; ++probe) {\n        X1UniformFastKeyState& entry =\n            uniform_fast_keys[(start + probe) & (X1_UNIFORM_FAST_KEY_CAPACITY - 1)];\n        if (entry.lock.test_and_set(std::memory_order_acquire)) {\n            continue;\n        }\n        if (!entry.occupied) {\n            entry.occupied = true;\n            entry.stage = stage;\n            entry.index = index;\n            entry.size = size;\n            entry.device_addr = device_addr;\n            entry.last_frame = frame;\n            entry.last_draw_serial = draw_serial;\n            entry.lock.clear(std::memory_order_release);\n            counters.uniform_fast_unique_keys.fetch_add(1, std::memory_order_relaxed);\n            return;\n        }\n        if (entry.stage != stage || entry.index != index || entry.size != size ||\n            entry.device_addr != device_addr) {\n            entry.lock.clear(std::memory_order_release);\n            continue;\n        }\n\n        counters.uniform_fast_repeat_key.fetch_add(1, std::memory_order_relaxed);\n        if (entry.last_frame == frame) {\n            counters.uniform_fast_same_frame.fetch_add(1, std::memory_order_relaxed);\n        }\n        if (draw_serial != 0 && entry.last_draw_serial == draw_serial) {\n            counters.uniform_fast_same_draw.fetch_add(1, std::memory_order_relaxed);\n        }\n        if (entry.last_frame + 1 == frame) {\n            counters.uniform_fast_consecutive_frame.fetch_add(1, std::memory_order_relaxed);\n        }\n        entry.last_frame = frame;\n        entry.last_draw_serial = draw_serial;\n        entry.lock.clear(std::memory_order_release);\n        return;\n    }\n\n    counters.uniform_fast_table_overflow.fetch_add(1, std::memory_order_relaxed);\n}\n\nvoid AdrenoProfiler::RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id,\n''',
        "uniform path record implementation",
    )

    text = replace_once(
        text,
        '''    const u64 alias_sync_copies = Take(counters.alias_sync_copies);\n''',
        '''    const u64 uniform_visits = Take(counters.uniform_visits);\n    const u64 uniform_bytes = Take(counters.uniform_bytes);\n    const u64 uniform_fast = Take(counters.uniform_fast);\n    const u64 uniform_fast_bytes = Take(counters.uniform_fast_bytes);\n    const u64 uniform_fast_alignment = Take(counters.uniform_fast_alignment);\n    const u64 uniform_fast_skip = Take(counters.uniform_fast_skip);\n    const u64 uniform_cached = Take(counters.uniform_cached);\n    const u64 uniform_cached_bytes = Take(counters.uniform_cached_bytes);\n    const u64 uniform_cached_clean = Take(counters.uniform_cached_clean);\n    const u64 uniform_cached_upload = Take(counters.uniform_cached_upload);\n    const u64 uniform_skip_policy_visits = Take(counters.uniform_skip_policy_visits);\n    const u64 uniform_fast_unique_keys = Take(counters.uniform_fast_unique_keys);\n    const u64 uniform_fast_repeat_key = Take(counters.uniform_fast_repeat_key);\n    const u64 uniform_fast_same_frame = Take(counters.uniform_fast_same_frame);\n    const u64 uniform_fast_same_draw = Take(counters.uniform_fast_same_draw);\n    const u64 uniform_fast_consecutive_frame = Take(counters.uniform_fast_consecutive_frame);\n    const u64 uniform_fast_table_overflow = Take(counters.uniform_fast_table_overflow);\n\n    const u64 alias_sync_copies = Take(counters.alias_sync_copies);\n''',
        "take uniform counters",
    )

    text = replace_once(
        text,
        '''    if (CorrelationEnabled()) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-ALIAS-SYNC] frame={} frames={} copies={} uniquePairs={} sameFrame={} "\n''',
        '''    if (CorrelationEnabled()) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-UNIFORM-PATH] frame={} frames={} visits={} bytes={} fast={} fastBytes={} "\n                 "fastAlignment={} fastSkip={} cached={} cachedBytes={} cachedClean={} "\n                 "cachedUpload={} skipPolicyVisits={} fastUniqueKeys={} fastRepeatKey={} "\n                 "fastSameFrame={} fastSameDraw={} fastConsecutiveFrame={} tableOverflow={} "\n                 "tableCapacity={} probeLimit={}",\n                 frame, frames, uniform_visits, uniform_bytes, uniform_fast, uniform_fast_bytes,\n                 uniform_fast_alignment, uniform_fast_skip, uniform_cached, uniform_cached_bytes,\n                 uniform_cached_clean, uniform_cached_upload, uniform_skip_policy_visits,\n                 uniform_fast_unique_keys, uniform_fast_repeat_key, uniform_fast_same_frame,\n                 uniform_fast_same_draw, uniform_fast_consecutive_frame,\n                 uniform_fast_table_overflow, X1_UNIFORM_FAST_KEY_CAPACITY,\n                 X1_UNIFORM_FAST_PROBE_LIMIT);\n    }\n\n    for (auto& entry : uniform_fast_keys) {\n        while (entry.lock.test_and_set(std::memory_order_acquire)) {\n        }\n        entry.occupied = false;\n        entry.stage = 0;\n        entry.index = 0;\n        entry.size = 0;\n        entry.device_addr = 0;\n        entry.last_frame = 0;\n        entry.last_draw_serial = 0;\n        entry.lock.clear(std::memory_order_release);\n    }\n\n    if (CorrelationEnabled()) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-ALIAS-SYNC] frame={} frames={} copies={} uniquePairs={} sameFrame={} "\n''',
        "uniform aggregate report and rotation",
    )
    profiler_cpp.write_text(text, encoding="utf-8")

    generic = root / "src/video_core/buffer_cache/buffer_cache.h"
    text = generic.read_text(encoding="utf-8")
    for marker in (
        "u32 dirty = ~0U;",
        "if constexpr (HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS)",
        "++channel_state->uniform_cache_shots[0];",
        "const bool use_fast_buffer = needs_alignment_stream",
        "const std::span<u8> span = runtime.BindMappedUniformBuffer(stage, binding_index, size);",
        "device_memory.ReadBlockUnsafe(device_addr, span.data(), size);",
        "if (SynchronizeBuffer(buffer, device_addr, size))",
    ):
        if marker not in text:
            raise RuntimeError(f"exact-dc95 Uniform semantic marker missing: {marker}")

    text = replace_once(
        text,
        '''        device_memory.ReadBlockUnsafe(device_addr, span.data(), size);\n        return;\n    }\n    // Classic cached path\n    if (SynchronizeBuffer(buffer, device_addr, size)) {\n        ++channel_state->uniform_cache_hits[0];\n    }\n''',
        '''        device_memory.ReadBlockUnsafe(device_addr, span.data(), size);\n        P::RecordX1UniformPath(stage, index, static_cast<u64>(device_addr), size, true,\n                               needs_alignment_stream, false,\n                               channel_state->uniform_buffer_skip_cache_size != 0);\n        return;\n    }\n    // Classic cached path\n    const bool x1_uniform_cached_clean = SynchronizeBuffer(buffer, device_addr, size);\n    if (x1_uniform_cached_clean) {\n        ++channel_state->uniform_cache_hits[0];\n    }\n    P::RecordX1UniformPath(stage, index, static_cast<u64>(device_addr), size, false, false,\n                           x1_uniform_cached_clean,\n                           channel_state->uniform_buffer_skip_cache_size != 0);\n''',
        "graphics Uniform path telemetry calls",
    )
    generic.write_text(text, encoding="utf-8")

    vk_header = vulkan / "vk_buffer_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    if '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"' not in text:
        text = replace_once(
            text,
            '#include "video_core/renderer_vulkan/vk_compute_pass.h"\n',
            '#include "video_core/renderer_vulkan/vk_adreno_profiler.h"\n#include "video_core/renderer_vulkan/vk_compute_pass.h"\n',
            "Vulkan profiler include",
        )
    text = replace_once(
        text,
        '''    static constexpr bool IS_OPENGL = false;\n''',
        '''    static void RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size,\n                                    bool fast, bool alignment_stream, bool cached_clean,\n                                    bool skip_policy_active) {\n        AdrenoProfiler::Get().RecordX1UniformPath(stage, index, device_addr, size, fast,\n                                                  alignment_stream, cached_clean,\n                                                  skip_policy_active);\n    }\n\n    static constexpr bool IS_OPENGL = false;\n''',
        "Vulkan uniform telemetry bridge",
    )
    vk_header.write_text(text, encoding="utf-8")

    gl_header = root / "src/video_core/renderer_opengl/gl_buffer_cache.h"
    text = gl_header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    static constexpr bool IS_OPENGL = true;\n''',
        '''    static void RecordX1UniformPath(u32, u32, u64, u32, bool, bool, bool, bool) {}\n\n    static constexpr bool IS_OPENGL = true;\n''',
        "OpenGL uniform telemetry no-op bridge",
    )
    gl_header.write_text(text, encoding="utf-8")

    print("Applied X1 exact-dc95 Uniform stream/reuse telemetry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
