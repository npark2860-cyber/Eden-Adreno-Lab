#!/usr/bin/env python3
'''Add sampled full-payload fingerprints to exact-dc95 fast Uniform telemetry.

Expected order:
  - transplant_dc95_uniform_stream_reuse.py
  - this pass

Instrumentation-only. It never skips, reuses, caches, batches, reorders, or changes any Uniform
upload/binding/dirty state. Exactly 1/16 of fast Uniform keys are deterministically sampled by key;
for sampled visits, a 64-bit FNV-1a fingerprint is computed over the bytes already copied into the
mapped staging span. This adds no extra guest-memory read. Fingerprint equality is strong evidence
of identical payload bytes but is not a mathematical byte-by-byte proof because hashes can collide.
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
        raise SystemExit("usage: transplant_dc95_uniform_payload_fingerprint.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    profiler_h = vulkan / "vk_adreno_profiler.h"
    if "RecordX1UniformPath" not in profiler_h.read_text(encoding="utf-8"):
        parent = Path(__file__).with_name("transplant_dc95_uniform_stream_reuse.py")
        subprocess.run([sys.executable, str(parent), str(root)], check=True)

    text = profiler_h.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    void RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size, bool fast,\n                             bool alignment_stream, bool cached_clean,\n                             bool skip_policy_active) noexcept;\n''',
        '''    void RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size, bool fast,\n                             bool alignment_stream, bool cached_clean,\n                             bool skip_policy_active, bool payload_sampled,\n                             u64 payload_fingerprint) noexcept;\n''',
        "Uniform payload profiler API",
    )
    text = replace_once(
        text,
        '''        std::atomic<u64> uniform_fast_table_overflow{0};\n\n        std::atomic<u64> alias_sync_copies{0};\n''',
        '''        std::atomic<u64> uniform_fast_table_overflow{0};\n        std::atomic<u64> uniform_payload_samples{0};\n        std::atomic<u64> uniform_payload_unique_samples{0};\n        std::atomic<u64> uniform_payload_repeat_samples{0};\n        std::atomic<u64> uniform_payload_same_fingerprint{0};\n        std::atomic<u64> uniform_payload_changed_fingerprint{0};\n        std::atomic<u64> uniform_payload_same_frame_same{0};\n        std::atomic<u64> uniform_payload_same_frame_changed{0};\n        std::atomic<u64> uniform_payload_sample_overflow{0};\n\n        std::atomic<u64> alias_sync_copies{0};\n''',
        "Uniform payload counters",
    )
    text = replace_once(
        text,
        '''        u64 last_frame{};\n        u64 last_draw_serial{};\n    };\n''',
        '''        u64 last_frame{};\n        u64 last_draw_serial{};\n        bool payload_valid{};\n        u64 payload_fingerprint{};\n    };\n''',
        "Uniform fast-key payload state",
    )
    profiler_h.write_text(text, encoding="utf-8")

    profiler_cpp = vulkan / "vk_adreno_profiler.cpp"
    text = profiler_cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''void AdrenoProfiler::RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size,\n                                             bool fast, bool alignment_stream, bool cached_clean,\n                                             bool skip_policy_active) noexcept {\n''',
        '''void AdrenoProfiler::RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size,\n                                             bool fast, bool alignment_stream, bool cached_clean,\n                                             bool skip_policy_active, bool payload_sampled,\n                                             u64 payload_fingerprint) noexcept {\n''',
        "Uniform payload record signature",
    )
    text = replace_once(
        text,
        '''    counters.uniform_fast.fetch_add(1, std::memory_order_relaxed);\n    counters.uniform_fast_bytes.fetch_add(size, std::memory_order_relaxed);\n''',
        '''    counters.uniform_fast.fetch_add(1, std::memory_order_relaxed);\n    counters.uniform_fast_bytes.fetch_add(size, std::memory_order_relaxed);\n    if (payload_sampled) {\n        counters.uniform_payload_samples.fetch_add(1, std::memory_order_relaxed);\n    }\n''',
        "Uniform payload sample visits",
    )
    text = replace_once(
        text,
        '''            entry.last_frame = frame;\n            entry.last_draw_serial = draw_serial;\n            entry.lock.clear(std::memory_order_release);\n            counters.uniform_fast_unique_keys.fetch_add(1, std::memory_order_relaxed);\n            return;\n''',
        '''            entry.last_frame = frame;\n            entry.last_draw_serial = draw_serial;\n            entry.payload_valid = payload_sampled;\n            entry.payload_fingerprint = payload_fingerprint;\n            entry.lock.clear(std::memory_order_release);\n            counters.uniform_fast_unique_keys.fetch_add(1, std::memory_order_relaxed);\n            if (payload_sampled) {\n                counters.uniform_payload_unique_samples.fetch_add(1, std::memory_order_relaxed);\n            }\n            return;\n''',
        "Uniform payload first-key state",
    )
    text = replace_once(
        text,
        '''        counters.uniform_fast_repeat_key.fetch_add(1, std::memory_order_relaxed);\n        if (entry.last_frame == frame) {\n            counters.uniform_fast_same_frame.fetch_add(1, std::memory_order_relaxed);\n        }\n''',
        '''        counters.uniform_fast_repeat_key.fetch_add(1, std::memory_order_relaxed);\n        if (payload_sampled && entry.payload_valid) {\n            counters.uniform_payload_repeat_samples.fetch_add(1, std::memory_order_relaxed);\n            if (entry.payload_fingerprint == payload_fingerprint) {\n                counters.uniform_payload_same_fingerprint.fetch_add(1, std::memory_order_relaxed);\n                if (entry.last_frame == frame) {\n                    counters.uniform_payload_same_frame_same.fetch_add(1, std::memory_order_relaxed);\n                }\n            } else {\n                counters.uniform_payload_changed_fingerprint.fetch_add(1, std::memory_order_relaxed);\n                if (entry.last_frame == frame) {\n                    counters.uniform_payload_same_frame_changed.fetch_add(1, std::memory_order_relaxed);\n                }\n            }\n            entry.payload_fingerprint = payload_fingerprint;\n        } else if (payload_sampled) {\n            entry.payload_valid = true;\n            entry.payload_fingerprint = payload_fingerprint;\n        }\n        if (entry.last_frame == frame) {\n            counters.uniform_fast_same_frame.fetch_add(1, std::memory_order_relaxed);\n        }\n''',
        "Uniform payload repeat comparison",
    )
    text = replace_once(
        text,
        '''    counters.uniform_fast_table_overflow.fetch_add(1, std::memory_order_relaxed);\n}\n\nvoid AdrenoProfiler::RecordX1AliasSyncCopy''',
        '''    counters.uniform_fast_table_overflow.fetch_add(1, std::memory_order_relaxed);\n    if (payload_sampled) {\n        counters.uniform_payload_sample_overflow.fetch_add(1, std::memory_order_relaxed);\n    }\n}\n\nvoid AdrenoProfiler::RecordX1AliasSyncCopy''',
        "Uniform payload sample overflow",
    )
    text = replace_once(
        text,
        '''    const u64 uniform_fast_table_overflow = Take(counters.uniform_fast_table_overflow);\n\n    const u64 alias_sync_copies = Take(counters.alias_sync_copies);\n''',
        '''    const u64 uniform_fast_table_overflow = Take(counters.uniform_fast_table_overflow);\n    const u64 uniform_payload_samples = Take(counters.uniform_payload_samples);\n    const u64 uniform_payload_unique_samples = Take(counters.uniform_payload_unique_samples);\n    const u64 uniform_payload_repeat_samples = Take(counters.uniform_payload_repeat_samples);\n    const u64 uniform_payload_same_fingerprint = Take(counters.uniform_payload_same_fingerprint);\n    const u64 uniform_payload_changed_fingerprint =\n        Take(counters.uniform_payload_changed_fingerprint);\n    const u64 uniform_payload_same_frame_same = Take(counters.uniform_payload_same_frame_same);\n    const u64 uniform_payload_same_frame_changed =\n        Take(counters.uniform_payload_same_frame_changed);\n    const u64 uniform_payload_sample_overflow = Take(counters.uniform_payload_sample_overflow);\n\n    const u64 alias_sync_copies = Take(counters.alias_sync_copies);\n''',
        "Take Uniform payload counters",
    )
    text = replace_once(
        text,
        '''    for (auto& entry : uniform_fast_keys) {\n''',
        '''    if (CorrelationEnabled()) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-UNIFORM-PAYLOAD] frame={} frames={} samples={} uniqueSamples={} "\n                 "repeatSamples={} sameFingerprint={} changedFingerprint={} "\n                 "sameFrameSame={} sameFrameChanged={} sampleOverflow={} sampleDenom=16",\n                 frame, frames, uniform_payload_samples, uniform_payload_unique_samples,\n                 uniform_payload_repeat_samples, uniform_payload_same_fingerprint,\n                 uniform_payload_changed_fingerprint, uniform_payload_same_frame_same,\n                 uniform_payload_same_frame_changed, uniform_payload_sample_overflow);\n    }\n\n    for (auto& entry : uniform_fast_keys) {\n''',
        "Uniform payload report",
    )
    text = replace_once(
        text,
        '''        entry.last_frame = 0;\n        entry.last_draw_serial = 0;\n        entry.lock.clear(std::memory_order_release);\n''',
        '''        entry.last_frame = 0;\n        entry.last_draw_serial = 0;\n        entry.payload_valid = false;\n        entry.payload_fingerprint = 0;\n        entry.lock.clear(std::memory_order_release);\n''',
        "Uniform payload state rotation",
    )
    profiler_cpp.write_text(text, encoding="utf-8")

    generic = root / "src/video_core/buffer_cache/buffer_cache.h"
    text = generic.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        device_memory.ReadBlockUnsafe(device_addr, span.data(), size);\n        P::RecordX1UniformPath(stage, index, static_cast<u64>(device_addr), size, true,\n                               needs_alignment_stream, false,\n                               channel_state->uniform_buffer_skip_cache_size != 0);\n        return;\n''',
        '''        device_memory.ReadBlockUnsafe(device_addr, span.data(), size);\n        u64 x1_uniform_sample_hash = static_cast<u64>(device_addr) ^\n                                     (static_cast<u64>(size) << 17) ^\n                                     (static_cast<u64>(stage) << 7) ^ static_cast<u64>(index);\n        x1_uniform_sample_hash ^= x1_uniform_sample_hash >> 33;\n        x1_uniform_sample_hash *= 0xff51afd7ed558ccdULL;\n        x1_uniform_sample_hash ^= x1_uniform_sample_hash >> 33;\n        const bool x1_uniform_payload_sampled = (x1_uniform_sample_hash & 15ULL) == 0;\n        u64 x1_uniform_payload_fingerprint = 14695981039346656037ULL;\n        if (x1_uniform_payload_sampled) {\n            for (const u8 byte : span) {\n                x1_uniform_payload_fingerprint ^= static_cast<u64>(byte);\n                x1_uniform_payload_fingerprint *= 1099511628211ULL;\n            }\n        }\n        P::RecordX1UniformPath(stage, index, static_cast<u64>(device_addr), size, true,\n                               needs_alignment_stream, false,\n                               channel_state->uniform_buffer_skip_cache_size != 0,\n                               x1_uniform_payload_sampled, x1_uniform_payload_fingerprint);\n        return;\n''',
        "Sampled full-payload fingerprint",
    )
    text = replace_once(
        text,
        '''    P::RecordX1UniformPath(stage, index, static_cast<u64>(device_addr), size, false, false,\n                           x1_uniform_cached_clean,\n                           channel_state->uniform_buffer_skip_cache_size != 0);\n''',
        '''    P::RecordX1UniformPath(stage, index, static_cast<u64>(device_addr), size, false, false,\n                           x1_uniform_cached_clean,\n                           channel_state->uniform_buffer_skip_cache_size != 0, false, 0);\n''',
        "Cached path payload telemetry arguments",
    )
    generic.write_text(text, encoding="utf-8")

    vk_header = vulkan / "vk_buffer_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    static void RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size,\n                                    bool fast, bool alignment_stream, bool cached_clean,\n                                    bool skip_policy_active) {\n        AdrenoProfiler::Get().RecordX1UniformPath(stage, index, device_addr, size, fast,\n                                                  alignment_stream, cached_clean,\n                                                  skip_policy_active);\n    }\n''',
        '''    static void RecordX1UniformPath(u32 stage, u32 index, u64 device_addr, u32 size,\n                                    bool fast, bool alignment_stream, bool cached_clean,\n                                    bool skip_policy_active, bool payload_sampled,\n                                    u64 payload_fingerprint) {\n        AdrenoProfiler::Get().RecordX1UniformPath(stage, index, device_addr, size, fast,\n                                                  alignment_stream, cached_clean,\n                                                  skip_policy_active, payload_sampled,\n                                                  payload_fingerprint);\n    }\n''',
        "Vulkan Uniform payload bridge",
    )
    vk_header.write_text(text, encoding="utf-8")

    gl_header = root / "src/video_core/renderer_opengl/gl_buffer_cache.h"
    text = gl_header.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    static void RecordX1UniformPath(u32, u32, u64, u32, bool, bool, bool, bool) {}\n''',
        '''    static void RecordX1UniformPath(u32, u32, u64, u32, bool, bool, bool, bool, bool, u64) {}\n''',
        "OpenGL Uniform payload no-op bridge",
    )
    gl_header.write_text(text, encoding="utf-8")

    print("Applied X1 exact-dc95 sampled Uniform payload fingerprint telemetry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
