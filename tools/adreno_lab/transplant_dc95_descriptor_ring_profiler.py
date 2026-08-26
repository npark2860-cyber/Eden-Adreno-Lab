#!/usr/bin/env python3
from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_descriptor_ring_profiler.py <eden-root>")

    root = Path(sys.argv[1])
    vulkan = root / "src/video_core/renderer_vulkan"

    header = r'''// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>
#include <chrono>

#include "common/common_types.h"

namespace Vulkan {

class DescriptorRingProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static DescriptorRingProfiler& Get();

    void Initialize(bool is_qualcomm_proprietary);

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    static TimePoint Now() noexcept {
        return Clock::now();
    }

    static u64 ElapsedNs(TimePoint start) noexcept {
        return static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count());
    }

    void FrameEnd();
    void RecordAllocation(u64 bytes);
    void RecordFrameReuseWait(u64 nanoseconds);
    void RecordChunkSwitch();
    void RecordExhaustionFinish(u64 nanoseconds);

private:
    DescriptorRingProfiler();

    static bool ParseEnabled();
    static u32 ParseReportFrames();

    struct Counters {
        std::atomic<u64> allocations{0};
        std::atomic<u64> allocation_bytes{0};
        std::atomic<u64> frame_reuse_waits{0};
        std::atomic<u64> frame_reuse_wait_ns{0};
        std::atomic<u64> chunk_switches{0};
        std::atomic<u64> exhaustion_finishes{0};
        std::atomic<u64> exhaustion_finish_ns{0};
    } counters;

    const bool requested;
    const u32 report_every_frames;
    std::atomic<bool> enabled{false};
    u64 frames_since_report{};
};

} // namespace Vulkan
'''

    source = r'''// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"

#include <algorithm>
#include <cstdlib>
#include <string_view>

#include "common/logging.h"

namespace Vulkan {
namespace {

u64 Take(std::atomic<u64>& value) {
    return value.exchange(0, std::memory_order_relaxed);
}

double PerFrame(u64 value, u64 frames) {
    return frames == 0 ? 0.0 : static_cast<double>(value) / static_cast<double>(frames);
}

double ToMs(u64 nanoseconds) {
    return static_cast<double>(nanoseconds) / 1'000'000.0;
}

double ToKiB(u64 bytes) {
    return static_cast<double>(bytes) / 1024.0;
}

} // Anonymous namespace

DescriptorRingProfiler& DescriptorRingProfiler::Get() {
    static DescriptorRingProfiler profiler;
    return profiler;
}

DescriptorRingProfiler::DescriptorRingProfiler()
    : requested{ParseEnabled()}, report_every_frames{ParseReportFrames()} {}

bool DescriptorRingProfiler::ParseEnabled() {
    const char* const raw = std::getenv("EDEN_X1_DESCRIPTOR_PROFILE");
    if (!raw) {
        return false;
    }
    const std::string_view value{raw};
    return value == "1" || value == "true" || value == "TRUE" || value == "on" ||
           value == "ON";
}

u32 DescriptorRingProfiler::ParseReportFrames() {
    const char* const raw = std::getenv("EDEN_X1_DESCRIPTOR_PROFILE_FRAMES");
    if (!raw) {
        return 120;
    }
    char* end{};
    const unsigned long parsed = std::strtoul(raw, &end, 10);
    if (end == raw || *end != '\0') {
        return 120;
    }
    return static_cast<u32>(std::clamp(parsed, 1UL, 3600UL));
}

void DescriptorRingProfiler::Initialize(bool is_qualcomm_proprietary) {
    const bool active = requested && is_qualcomm_proprietary;
    enabled.store(active, std::memory_order_relaxed);
    if (active) {
        LOG_INFO(Render_Vulkan,
                 "[X1-DBUF] descriptor-ring profiler enabled; report interval={} frames",
                 report_every_frames);
    } else if (requested) {
        LOG_WARNING(Render_Vulkan,
                    "[X1-DBUF] profiling requested on a non-Qualcomm proprietary Vulkan driver; "
                    "profiler disabled");
    }
}

void DescriptorRingProfiler::FrameEnd() {
    if (!Enabled()) {
        return;
    }
    ++frames_since_report;
    if (frames_since_report < report_every_frames) {
        return;
    }

    const u64 frames = frames_since_report;
    frames_since_report = 0;

    const u64 allocations = Take(counters.allocations);
    const u64 allocation_bytes = Take(counters.allocation_bytes);
    const u64 frame_reuse_waits = Take(counters.frame_reuse_waits);
    const u64 frame_reuse_wait_ns = Take(counters.frame_reuse_wait_ns);
    const u64 chunk_switches = Take(counters.chunk_switches);
    const u64 exhaustion_finishes = Take(counters.exhaustion_finishes);
    const u64 exhaustion_finish_ns = Take(counters.exhaustion_finish_ns);

    LOG_INFO(Render_Vulkan,
             "[X1-DBUF] frames={} | alloc={} bytes={} ({:.1f} KiB/f) | reuseWait={} "
             "{:.3f}ms | chunkSwitch={} ({:.2f}/f) | exhaustionFinish={} {:.3f}ms",
             frames, allocations, allocation_bytes, PerFrame(ToKiB(allocation_bytes), frames),
             frame_reuse_waits, ToMs(frame_reuse_wait_ns), chunk_switches,
             PerFrame(chunk_switches, frames), exhaustion_finishes, ToMs(exhaustion_finish_ns));
}

void DescriptorRingProfiler::RecordAllocation(u64 bytes) {
    if (!Enabled()) {
        return;
    }
    counters.allocations.fetch_add(1, std::memory_order_relaxed);
    counters.allocation_bytes.fetch_add(bytes, std::memory_order_relaxed);
}

void DescriptorRingProfiler::RecordFrameReuseWait(u64 nanoseconds) {
    if (!Enabled()) {
        return;
    }
    counters.frame_reuse_waits.fetch_add(1, std::memory_order_relaxed);
    counters.frame_reuse_wait_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
}

void DescriptorRingProfiler::RecordChunkSwitch() {
    if (Enabled()) {
        counters.chunk_switches.fetch_add(1, std::memory_order_relaxed);
    }
}

void DescriptorRingProfiler::RecordExhaustionFinish(u64 nanoseconds) {
    if (!Enabled()) {
        return;
    }
    counters.exhaustion_finishes.fetch_add(1, std::memory_order_relaxed);
    counters.exhaustion_finish_ns.fetch_add(nanoseconds, std::memory_order_relaxed);
}

} // namespace Vulkan
'''

    (vulkan / "vk_descriptor_ring_profiler.h").write_text(header, encoding="utf-8")
    (vulkan / "vk_descriptor_ring_profiler.cpp").write_text(source, encoding="utf-8")

    cmake = root / "src/video_core/CMakeLists.txt"
    text = cmake.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    renderer_vulkan/vk_descriptor_buffer.cpp\n    renderer_vulkan/vk_descriptor_buffer.h\n",
        "    renderer_vulkan/vk_descriptor_buffer.cpp\n    renderer_vulkan/vk_descriptor_buffer.h\n"
        "    renderer_vulkan/vk_descriptor_ring_profiler.cpp\n"
        "    renderer_vulkan/vk_descriptor_ring_profiler.h\n",
        "CMake descriptor profiler registration",
    )
    cmake.write_text(text, encoding="utf-8")

    renderer = vulkan / "renderer_vulkan.cpp"
    text = renderer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/renderer_vulkan.h"\n',
        '#include "video_core/renderer_vulkan/renderer_vulkan.h"\n'
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n',
        "renderer include",
    )
    text = replace_once(
        text,
        "    , rasterizer(render_window, gpu, device_memory, device, memory_allocator, state_tracker, scheduler) {\n\n"
        "    if (Settings::values.renderer_force_max_clock.GetValue() && device.ShouldBoostClocks()) {",
        "    , rasterizer(render_window, gpu, device_memory, device, memory_allocator, state_tracker, scheduler) {\n\n"
        "    DescriptorRingProfiler::Get().Initialize(\n"
        "        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);\n\n"
        "    if (Settings::values.renderer_force_max_clock.GetValue() && device.ShouldBoostClocks()) {",
        "renderer initialize",
    )
    text = replace_once(
        text,
        "    gpu.RendererFrameEndNotify();\n    rasterizer.TickFrame();\n}",
        "    gpu.RendererFrameEndNotify();\n    rasterizer.TickFrame();\n"
        "    DescriptorRingProfiler::Get().FrameEnd();\n}",
        "renderer frame end",
    )
    renderer.write_text(text, encoding="utf-8")

    descriptor = vulkan / "vk_descriptor_buffer.cpp"
    text = descriptor.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "video_core/renderer_vulkan/vk_descriptor_buffer.h"\n',
        '#include "video_core/renderer_vulkan/vk_descriptor_buffer.h"\n'
        '#include "video_core/renderer_vulkan/vk_descriptor_ring_profiler.h"\n',
        "descriptor include",
    )
    text = replace_once(
        text,
        "    const VkDeviceSize needed{Common::AlignUp(size, alignment)};\n"
        "    if (frame_reused) {\n"
        "        frame_reused = false;\n"
        "        scheduler.Wait(frame_ticks[frame_index]);\n"
        "    }",
        "    const VkDeviceSize needed{Common::AlignUp(size, alignment)};\n"
        "    auto& profiler = DescriptorRingProfiler::Get();\n"
        "    profiler.RecordAllocation(needed);\n"
        "    if (frame_reused) {\n"
        "        frame_reused = false;\n"
        "        if (profiler.Enabled()) {\n"
        "            const auto wait_start = DescriptorRingProfiler::Now();\n"
        "            scheduler.Wait(frame_ticks[frame_index]);\n"
        "            profiler.RecordFrameReuseWait(DescriptorRingProfiler::ElapsedNs(wait_start));\n"
        "        } else {\n"
        "            scheduler.Wait(frame_ticks[frame_index]);\n"
        "        }\n"
        "    }",
        "frame reuse wait",
    )
    text = replace_once(
        text,
        "        if (chunk_cursor + 1 < chunks_per_frame) {\n"
        "            ++chunk_cursor;\n"
        "        } else {\n"
        "            LOG_DEBUG(Render_Vulkan, \"Descriptor buffer frame exhausted, stalling on the GPU\");\n"
        "            scheduler.Finish();\n"
        "            chunk_cursor = 0;\n"
        "            ++generation;\n"
        "        }",
        "        if (chunk_cursor + 1 < chunks_per_frame) {\n"
        "            ++chunk_cursor;\n"
        "            profiler.RecordChunkSwitch();\n"
        "        } else {\n"
        "            LOG_DEBUG(Render_Vulkan, \"Descriptor buffer frame exhausted, stalling on the GPU\");\n"
        "            if (profiler.Enabled()) {\n"
        "                const auto finish_start = DescriptorRingProfiler::Now();\n"
        "                scheduler.Finish();\n"
        "                profiler.RecordExhaustionFinish(\n"
        "                    DescriptorRingProfiler::ElapsedNs(finish_start));\n"
        "            } else {\n"
        "                scheduler.Finish();\n"
        "            }\n"
        "            chunk_cursor = 0;\n"
        "            ++generation;\n"
        "        }",
        "chunk/exhaustion instrumentation",
    )
    descriptor.write_text(text, encoding="utf-8")

    print("Transplanted minimal dc95 descriptor-ring profiler")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
