#!/usr/bin/env python3
'''Add bounded passive telemetry for alias copies requested by SynchronizeAliases().

Expected order:
  - transplant_dc95_alias_copy_reasons.py
  - this pass

Instrumentation-only. No copy, barrier, render-pass, modification-tick, alias-state,
or Draw/Dispatch behavior is changed. The tracker is fixed-size and is reset at the
existing profiler report boundary; the alias-copy hot path emits no per-copy logs.
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
        raise SystemExit("usage: transplant_dc95_alias_sync_redundancy.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    header = vulkan / "vk_adreno_profiler.h"
    if "OtherTextureAliasDirectVkCopy" not in header.read_text(encoding="utf-8"):
        parent = Path(__file__).with_name("transplant_dc95_alias_copy_reasons.py")
        subprocess.run([sys.executable, str(parent), str(root)], check=True)

    # Profiler API, fixed bounded pair state, and aggregate counters.
    text = header.read_text(encoding="utf-8")
    old = '''    bool PushBufferCategoryOverrideIf(BufferCategory expected, BufferCategory category) noexcept;\n'''
    new = '''    bool PushBufferCategoryOverrideIf(BufferCategory expected, BufferCategory category) noexcept;\n    void RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id, u64 texture_frame,\n                               u64 source_modification_tick, u32 region_count,\n                               u64 region_signature) noexcept;\n'''
    text = replace_once(text, old, new, "alias-sync profiler API")

    old = '''        std::atomic<u64> present_waits{0};\n'''
    new = '''        std::atomic<u64> alias_sync_copies{0};\n        std::atomic<u64> alias_sync_unique_pairs{0};\n        std::atomic<u64> alias_sync_same_frame{0};\n        std::atomic<u64> alias_sync_same_draw{0};\n        std::atomic<u64> alias_sync_consecutive_frame{0};\n        std::atomic<u64> alias_sync_same_src_tick{0};\n        std::atomic<u64> alias_sync_advanced_src_tick{0};\n        std::atomic<u64> alias_sync_regressed_src_tick{0};\n        std::atomic<u64> alias_sync_same_signature{0};\n        std::atomic<u64> alias_sync_same_state_signature{0};\n        std::atomic<u64> alias_sync_regions{0};\n        std::atomic<u64> alias_sync_max_regions{0};\n        std::atomic<u64> alias_sync_table_overflow{0};\n\n        std::atomic<u64> present_waits{0};\n'''
    text = replace_once(text, old, new, "alias-sync aggregate counters")

    old = '''    const u32 report_every_frames;\n'''
    new = '''    static constexpr size_t X1_ALIAS_SYNC_PAIR_CAPACITY = 4096;\n    static constexpr size_t X1_ALIAS_SYNC_PROBE_LIMIT = 32;\n\n    struct X1AliasSyncPairState {\n        std::atomic_flag lock = ATOMIC_FLAG_INIT;\n        bool occupied{};\n        u64 key{};\n        u64 last_frame{};\n        u64 last_draw_serial{};\n        u64 last_src_tick{};\n        u64 last_signature{};\n    };\n\n    std::array<X1AliasSyncPairState, X1_ALIAS_SYNC_PAIR_CAPACITY> alias_sync_pairs{};\n\n    const u32 report_every_frames;\n'''
    text = replace_once(text, old, new, "bounded alias-sync pair table")
    header.write_text(text, encoding="utf-8")

    cpp = vulkan / "vk_adreno_profiler.cpp"
    text = cpp.read_text(encoding="utf-8")

    old = '''struct WorkCorrelationState {\n    AdrenoProfiler::WorkOrigin origin{AdrenoProfiler::WorkOrigin::None};\n    u64 signature{};\n'''
    new = '''struct WorkCorrelationState {\n    AdrenoProfiler::WorkOrigin origin{AdrenoProfiler::WorkOrigin::None};\n    u64 serial{};\n    u64 signature{};\n'''
    text = replace_once(text, old, new, "work serial field")

    old = '''thread_local WorkCorrelationState work_correlation{};\n'''
    new = '''thread_local WorkCorrelationState work_correlation{};\nthread_local u64 work_serial_counter{};\n'''
    text = replace_once(text, old, new, "thread-local work serial counter")

    old = '''    work_correlation = WorkCorrelationState{};\n    work_correlation.origin = origin;\n}\n\nvoid AdrenoProfiler::SetWorkSignature'''
    new = '''    work_correlation = WorkCorrelationState{};\n    work_correlation.origin = origin;\n    const u64 local_serial = ++work_serial_counter;\n    work_correlation.serial = (static_cast<u64>(ThreadId()) << 32) ^ local_serial;\n}\n\nvoid AdrenoProfiler::SetWorkSignature'''
    text = replace_once(text, old, new, "stable Draw work serial")

    old = '''void AdrenoProfiler::EndWork() {\n'''
    new = '''void AdrenoProfiler::RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id,\n                                              u64 texture_frame,\n                                              u64 source_modification_tick, u32 region_count,\n                                              u64 region_signature) noexcept {\n    if (!CorrelationEnabled()) {\n        return;\n    }\n\n    counters.alias_sync_copies.fetch_add(1, std::memory_order_relaxed);\n    counters.alias_sync_regions.fetch_add(region_count, std::memory_order_relaxed);\n    u64 max_regions = counters.alias_sync_max_regions.load(std::memory_order_relaxed);\n    while (max_regions < region_count &&\n           !counters.alias_sync_max_regions.compare_exchange_weak(\n               max_regions, region_count, std::memory_order_relaxed)) {\n    }\n\n    const u64 key = (static_cast<u64>(dst_image_id) << 32) | src_image_id;\n    u64 hash = key;\n    hash ^= hash >> 33;\n    hash *= 0xff51afd7ed558ccdULL;\n    hash ^= hash >> 33;\n    hash *= 0xc4ceb9fe1a85ec53ULL;\n    hash ^= hash >> 33;\n    const size_t start = static_cast<size_t>(hash) & (X1_ALIAS_SYNC_PAIR_CAPACITY - 1);\n    const u64 draw_serial = work_correlation.origin == WorkOrigin::Draw ? work_correlation.serial : 0;\n\n    for (size_t probe = 0; probe < X1_ALIAS_SYNC_PROBE_LIMIT; ++probe) {\n        X1AliasSyncPairState& entry =\n            alias_sync_pairs[(start + probe) & (X1_ALIAS_SYNC_PAIR_CAPACITY - 1)];\n        if (entry.lock.test_and_set(std::memory_order_acquire)) {\n            continue;\n        }\n\n        if (!entry.occupied) {\n            entry.occupied = true;\n            entry.key = key;\n            entry.last_frame = texture_frame;\n            entry.last_draw_serial = draw_serial;\n            entry.last_src_tick = source_modification_tick;\n            entry.last_signature = region_signature;\n            entry.lock.clear(std::memory_order_release);\n            counters.alias_sync_unique_pairs.fetch_add(1, std::memory_order_relaxed);\n            return;\n        }\n\n        if (entry.key != key) {\n            entry.lock.clear(std::memory_order_release);\n            continue;\n        }\n\n        const bool same_frame = entry.last_frame == texture_frame;\n        const bool same_draw = draw_serial != 0 && entry.last_draw_serial == draw_serial;\n        const bool consecutive_frame = entry.last_frame + 1 == texture_frame;\n        const bool same_src_tick = entry.last_src_tick == source_modification_tick;\n        const bool advanced_src_tick = entry.last_src_tick < source_modification_tick;\n        const bool regressed_src_tick = entry.last_src_tick > source_modification_tick;\n        const bool same_signature = entry.last_signature == region_signature;\n\n        if (same_frame) counters.alias_sync_same_frame.fetch_add(1, std::memory_order_relaxed);\n        if (same_draw) counters.alias_sync_same_draw.fetch_add(1, std::memory_order_relaxed);\n        if (consecutive_frame) {\n            counters.alias_sync_consecutive_frame.fetch_add(1, std::memory_order_relaxed);\n        }\n        if (same_src_tick) {\n            counters.alias_sync_same_src_tick.fetch_add(1, std::memory_order_relaxed);\n        } else if (advanced_src_tick) {\n            counters.alias_sync_advanced_src_tick.fetch_add(1, std::memory_order_relaxed);\n        } else if (regressed_src_tick) {\n            counters.alias_sync_regressed_src_tick.fetch_add(1, std::memory_order_relaxed);\n        }\n        if (same_signature) {\n            counters.alias_sync_same_signature.fetch_add(1, std::memory_order_relaxed);\n        }\n        if (same_src_tick && same_signature) {\n            counters.alias_sync_same_state_signature.fetch_add(1, std::memory_order_relaxed);\n        }\n\n        entry.last_frame = texture_frame;\n        entry.last_draw_serial = draw_serial;\n        entry.last_src_tick = source_modification_tick;\n        entry.last_signature = region_signature;\n        entry.lock.clear(std::memory_order_release);\n        return;\n    }\n\n    counters.alias_sync_table_overflow.fetch_add(1, std::memory_order_relaxed);\n}\n\nvoid AdrenoProfiler::EndWork() {\n'''
    text = replace_once(text, old, new, "alias-sync record implementation")

    old = '''    const u64 present_waits = Take(counters.present_waits);\n'''
    new = '''    const u64 alias_sync_copies = Take(counters.alias_sync_copies);\n    const u64 alias_sync_unique_pairs = Take(counters.alias_sync_unique_pairs);\n    const u64 alias_sync_same_frame = Take(counters.alias_sync_same_frame);\n    const u64 alias_sync_same_draw = Take(counters.alias_sync_same_draw);\n    const u64 alias_sync_consecutive_frame = Take(counters.alias_sync_consecutive_frame);\n    const u64 alias_sync_same_src_tick = Take(counters.alias_sync_same_src_tick);\n    const u64 alias_sync_advanced_src_tick = Take(counters.alias_sync_advanced_src_tick);\n    const u64 alias_sync_regressed_src_tick = Take(counters.alias_sync_regressed_src_tick);\n    const u64 alias_sync_same_signature = Take(counters.alias_sync_same_signature);\n    const u64 alias_sync_same_state_signature = Take(counters.alias_sync_same_state_signature);\n    const u64 alias_sync_regions = Take(counters.alias_sync_regions);\n    const u64 alias_sync_max_regions = Take(counters.alias_sync_max_regions);\n    const u64 alias_sync_table_overflow = Take(counters.alias_sync_table_overflow);\n\n    const u64 present_waits = Take(counters.present_waits);\n'''
    text = replace_once(text, old, new, "take alias-sync counters")

    old = '''    if (QcomEnabled()) {\n        LOG_INFO(Render_Vulkan,\n'''
    new = '''    if (CorrelationEnabled()) {\n        LOG_INFO(Render_Vulkan,\n                 "[X1-ALIAS-SYNC] frame={} frames={} copies={} uniquePairs={} sameFrame={} "\n                 "sameDraw={} consecutiveFrame={} sameSrcTick={} advancedSrcTick={} "\n                 "regressedSrcTick={} sameSignature={} sameStateSignature={} regions={} "\n                 "maxRegions={} tableOverflow={} tableCapacity={} probeLimit={}",\n                 frame, frames, alias_sync_copies, alias_sync_unique_pairs, alias_sync_same_frame,\n                 alias_sync_same_draw, alias_sync_consecutive_frame, alias_sync_same_src_tick,\n                 alias_sync_advanced_src_tick, alias_sync_regressed_src_tick,\n                 alias_sync_same_signature, alias_sync_same_state_signature, alias_sync_regions,\n                 alias_sync_max_regions, alias_sync_table_overflow, X1_ALIAS_SYNC_PAIR_CAPACITY,\n                 X1_ALIAS_SYNC_PROBE_LIMIT);\n    }\n\n    for (auto& entry : alias_sync_pairs) {\n        while (entry.lock.test_and_set(std::memory_order_acquire)) {\n        }\n        entry.occupied = false;\n        entry.key = 0;\n        entry.last_frame = 0;\n        entry.last_draw_serial = 0;\n        entry.last_src_tick = 0;\n        entry.last_signature = 0;\n        entry.lock.clear(std::memory_order_release);\n    }\n\n    if (QcomEnabled()) {\n        LOG_INFO(Render_Vulkan,\n'''
    text = replace_once(text, old, new, "alias-sync aggregate report and rotation")
    cpp.write_text(text, encoding="utf-8")

    # Vulkan bridge into the shared generic TextureCache code.
    vk_header = vulkan / "vk_texture_cache.h"
    text = vk_header.read_text(encoding="utf-8")
    old = '''    static bool BeginX1TextureSubcategoryIf(u32 expected, u32 category) {\n        return AdrenoProfiler::Get().PushBufferCategoryOverrideIf(\n            static_cast<AdrenoProfiler::BufferCategory>(expected),\n            static_cast<AdrenoProfiler::BufferCategory>(category));\n    }\n\n    using Runtime = Vulkan::TextureCacheRuntime;\n'''
    new = '''    static bool BeginX1TextureSubcategoryIf(u32 expected, u32 category) {\n        return AdrenoProfiler::Get().PushBufferCategoryOverrideIf(\n            static_cast<AdrenoProfiler::BufferCategory>(expected),\n            static_cast<AdrenoProfiler::BufferCategory>(category));\n    }\n\n    static bool X1AliasSyncTelemetryEnabled() {\n        return AdrenoProfiler::Get().CorrelationEnabled();\n    }\n\n    static void RecordX1AliasSyncCopy(u32 dst_image_id, u32 src_image_id, u64 texture_frame,\n                                      u64 source_modification_tick, u32 region_count,\n                                      u64 region_signature) {\n        AdrenoProfiler::Get().RecordX1AliasSyncCopy(dst_image_id, src_image_id, texture_frame,\n                                                    source_modification_tick, region_count,\n                                                    region_signature);\n    }\n\n    using Runtime = Vulkan::TextureCacheRuntime;\n'''
    text = replace_once(text, old, new, "Vulkan alias-sync bridge")
    vk_header.write_text(text, encoding="utf-8")

    gl_header = root / "src/video_core/renderer_opengl/gl_texture_cache.h"
    text = gl_header.read_text(encoding="utf-8")
    old = '''    static void EndX1TextureSubcategory() {}\n\n    using Runtime = OpenGL::TextureCacheRuntime;\n'''
    new = '''    static void EndX1TextureSubcategory() {}\n\n    static bool X1AliasSyncTelemetryEnabled() {\n        return false;\n    }\n\n    static void RecordX1AliasSyncCopy(u32, u32, u64, u64, u32, u64) {}\n\n    using Runtime = OpenGL::TextureCacheRuntime;\n'''
    text = replace_once(text, old, new, "OpenGL no-op alias-sync bridge")
    gl_header.write_text(text, encoding="utf-8")

    # Source-first semantic guards: the experiment is valid only for exact-dc95 behavior where
    # newer source aliases are selected by modification_tick and destination state is advanced to
    # the most recent selected tick before the copies execute.
    cache = root / "src/video_core/texture_cache/texture_cache.h"
    text = cache.read_text(encoding="utf-8")
    for marker in (
        "if (image.modification_tick < aliased_image.modification_tick)",
        "image.modification_tick = most_recent_tick;",
        "const auto x1_alias_copy = [this](ImageId dst_id, ImageId src_id, const auto& copies)",
    ):
        if marker not in text:
            raise RuntimeError(f"exact-dc95 alias semantic marker missing: {marker}")

    old = '''    const auto x1_alias_copy = [this](ImageId dst_id, ImageId src_id, const auto& copies) {\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(29);\n        }\n        CopyImage(dst_id, src_id, copies);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n    };\n'''
    new = '''    const auto x1_alias_copy = [this](ImageId dst_id, ImageId src_id, const auto& copies) {\n        if constexpr (requires {\n                          P::X1AliasSyncTelemetryEnabled();\n                          P::RecordX1AliasSyncCopy(u32{}, u32{}, u64{}, u64{}, u32{}, u64{});\n                      }) {\n            if (P::X1AliasSyncTelemetryEnabled()) {\n                constexpr u64 FNV_OFFSET = 1469598103934665603ULL;\n                constexpr u64 FNV_PRIME = 1099511628211ULL;\n                u64 signature = FNV_OFFSET;\n                const auto mix = [&signature](u32 value) {\n                    signature ^= static_cast<u64>(value);\n                    signature *= FNV_PRIME;\n                };\n                mix(static_cast<u32>(copies.size()));\n                for (const ImageCopy& copy : copies) {\n                    mix(static_cast<u32>(copy.src_subresource.base_level));\n                    mix(static_cast<u32>(copy.src_subresource.base_layer));\n                    mix(static_cast<u32>(copy.src_subresource.num_layers));\n                    mix(static_cast<u32>(copy.dst_subresource.base_level));\n                    mix(static_cast<u32>(copy.dst_subresource.base_layer));\n                    mix(static_cast<u32>(copy.dst_subresource.num_layers));\n                    mix(static_cast<u32>(copy.src_offset.x));\n                    mix(static_cast<u32>(copy.src_offset.y));\n                    mix(static_cast<u32>(copy.src_offset.z));\n                    mix(static_cast<u32>(copy.dst_offset.x));\n                    mix(static_cast<u32>(copy.dst_offset.y));\n                    mix(static_cast<u32>(copy.dst_offset.z));\n                    mix(copy.extent.width);\n                    mix(copy.extent.height);\n                    mix(copy.extent.depth);\n                }\n                const Image& source = slot_images[src_id];\n                P::RecordX1AliasSyncCopy(dst_id.Value(), src_id.Value(), frame_tick,\n                                         source.modification_tick,\n                                         static_cast<u32>(copies.size()), signature);\n            }\n        }\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::BeginX1TextureSubcategory(29);\n        }\n        CopyImage(dst_id, src_id, copies);\n        if constexpr (requires {\n                          P::BeginX1TextureSubcategory(u32{});\n                          P::EndX1TextureSubcategory();\n                      }) {\n            P::EndX1TextureSubcategory();\n        }\n    };\n'''
    text = replace_once(text, old, new, "SynchronizeAliases request telemetry")
    cache.write_text(text, encoding="utf-8")

    print("Applied bounded passive SynchronizeAliases redundancy telemetry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
