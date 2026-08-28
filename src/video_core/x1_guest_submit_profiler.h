// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <mutex>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace VideoCore {

class X1GuestSubmitProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1GuestSubmitProfiler& Get() {
        static X1GuestSubmitProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_guest_submit_thread_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        std::scoped_lock lk(mutex);
        slots = {};
        overflow_submits = 0;
        report_start = Clock::now();
        frames_since_report = 0;
        frame_id.store(0, std::memory_order_relaxed);
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void RecordSubmitCaller(u64 thread_id, s64 cpu_ticks, s64 clock_ticks, u64 pc,
                            s32 current_core, s32 active_core, s32 priority,
                            u32 ioctl_kind) noexcept {
        if (!Enabled()) {
            return;
        }

        const u64 now_ns = NowNs();
        std::scoped_lock lk(mutex);

        Slot* slot = nullptr;
        for (auto& candidate : slots) {
            if (candidate.thread_id == thread_id) {
                slot = &candidate;
                break;
            }
        }
        if (slot == nullptr) {
            for (auto& candidate : slots) {
                if (candidate.thread_id == 0) {
                    candidate.thread_id = thread_id;
                    slot = &candidate;
                    break;
                }
            }
        }
        if (slot == nullptr) {
            ++overflow_submits;
            return;
        }

        ++slot->submits;
        if (ioctl_kind == 1) {
            ++slot->ioctl1;
        } else if (ioctl_kind == 2) {
            ++slot->ioctl2;
        }

        if (slot->last_wall_ns != 0 && now_ns >= slot->last_wall_ns) {
            const u64 wall_gap_ns = now_ns - slot->last_wall_ns;
            ++slot->gap_count;
            slot->wall_gap_ns += wall_gap_ns;
            if (wall_gap_ns > slot->wall_gap_max_ns) {
                slot->wall_gap_max_ns = wall_gap_ns;
            }

            if (clock_ticks >= slot->last_clock_ticks) {
                slot->clock_gap_ticks +=
                    static_cast<u64>(clock_ticks - slot->last_clock_ticks);
            }
            if (cpu_ticks >= slot->last_cpu_ticks) {
                slot->cpu_delta_ticks += static_cast<u64>(cpu_ticks - slot->last_cpu_ticks);
            }

            if (pc == slot->last_pc) {
                ++slot->same_pc;
            } else {
                ++slot->pc_changes;
            }
        }

        slot->last_wall_ns = now_ns;
        slot->last_cpu_ticks = cpu_ticks;
        slot->last_clock_ticks = clock_ticks;
        slot->last_pc = pc;
        slot->current_core = current_core;
        slot->active_core = active_core;
        slot->priority = priority;
    }

    void FrameEnd() {
        if (!Enabled()) {
            return;
        }

        const u64 frame = frame_id.fetch_add(1, std::memory_order_relaxed) + 1;
        ++frames_since_report;
        if (frames_since_report < ReportFrames) {
            return;
        }

        const auto now = Clock::now();
        const u64 wall_ns = report_start == TimePoint{}
                                ? 0
                                : static_cast<u64>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                                       now - report_start)
                                                       .count());
        report_start = now;
        const u64 frames = frames_since_report;
        frames_since_report = 0;

        Snapshot dominant{};
        u64 total_submits{};
        u64 active_threads{};
        u64 overflow{};

        {
            std::scoped_lock lk(mutex);
            overflow = overflow_submits;
            overflow_submits = 0;

            for (auto& slot : slots) {
                if (slot.thread_id == 0 || slot.submits == 0) {
                    continue;
                }
                ++active_threads;
                total_submits += slot.submits;
                if (slot.submits > dominant.submits) {
                    dominant = Snapshot::From(slot);
                }
                slot.ResetWindow();
            }
        }

        const double cpu_share = dominant.clock_gap_ticks == 0
                                     ? 0.0
                                     : 100.0 * static_cast<double>(dominant.cpu_delta_ticks) /
                                           static_cast<double>(dominant.clock_gap_ticks);
        const double dominant_share = total_submits == 0
                                          ? 0.0
                                          : 100.0 * static_cast<double>(dominant.submits) /
                                                static_cast<double>(total_submits);

        LOG_INFO(HW_GPU,
                 "[X1-GUESTSUBMIT] frame={} frames={} wall={:.3f}ms threads={} submits={} overflow={} "
                 "tid={:#x} domSubmits={} domShare={:.2f}% ioctl1={} ioctl2={} "
                 "gapN={} wallGap={:.3f}ms wallGapMax={:.3f}ms clockTicks={} cpuTicks={} cpuShare={:.2f}% "
                 "pc={:#x} samePc={} pcChange={} currentCore={} activeCore={} prio={}",
                 frame, frames, ToMs(wall_ns), active_threads, total_submits, overflow,
                 dominant.thread_id, dominant.submits, dominant_share, dominant.ioctl1,
                 dominant.ioctl2, dominant.gap_count, ToMs(dominant.wall_gap_ns),
                 ToMs(dominant.wall_gap_max_ns), dominant.clock_gap_ticks,
                 dominant.cpu_delta_ticks, cpu_share, dominant.last_pc, dominant.same_pc,
                 dominant.pc_changes, dominant.current_core, dominant.active_core,
                 dominant.priority);
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t MaxTrackedThreads = 8;

    struct Slot {
        u64 thread_id{};
        u64 last_wall_ns{};
        s64 last_cpu_ticks{};
        s64 last_clock_ticks{};
        u64 last_pc{};
        s32 current_core{-1};
        s32 active_core{-1};
        s32 priority{-1};

        u64 submits{};
        u64 ioctl1{};
        u64 ioctl2{};
        u64 gap_count{};
        u64 wall_gap_ns{};
        u64 wall_gap_max_ns{};
        u64 clock_gap_ticks{};
        u64 cpu_delta_ticks{};
        u64 same_pc{};
        u64 pc_changes{};

        void ResetWindow() noexcept {
            submits = 0;
            ioctl1 = 0;
            ioctl2 = 0;
            gap_count = 0;
            wall_gap_ns = 0;
            wall_gap_max_ns = 0;
            clock_gap_ticks = 0;
            cpu_delta_ticks = 0;
            same_pc = 0;
            pc_changes = 0;
        }
    };

    struct Snapshot {
        u64 thread_id{};
        u64 submits{};
        u64 ioctl1{};
        u64 ioctl2{};
        u64 gap_count{};
        u64 wall_gap_ns{};
        u64 wall_gap_max_ns{};
        u64 clock_gap_ticks{};
        u64 cpu_delta_ticks{};
        u64 last_pc{};
        u64 same_pc{};
        u64 pc_changes{};
        s32 current_core{-1};
        s32 active_core{-1};
        s32 priority{-1};

        static Snapshot From(const Slot& slot) noexcept {
            Snapshot out{};
            out.thread_id = slot.thread_id;
            out.submits = slot.submits;
            out.ioctl1 = slot.ioctl1;
            out.ioctl2 = slot.ioctl2;
            out.gap_count = slot.gap_count;
            out.wall_gap_ns = slot.wall_gap_ns;
            out.wall_gap_max_ns = slot.wall_gap_max_ns;
            out.clock_gap_ticks = slot.clock_gap_ticks;
            out.cpu_delta_ticks = slot.cpu_delta_ticks;
            out.last_pc = slot.last_pc;
            out.same_pc = slot.same_pc;
            out.pc_changes = slot.pc_changes;
            out.current_core = slot.current_core;
            out.active_core = slot.active_core;
            out.priority = slot.priority;
            return out;
        }
    };

    static u64 NowNs() noexcept {
        return static_cast<u64>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                    Clock::now().time_since_epoch())
                                    .count());
    }

    static double ToMs(u64 ns) noexcept {
        return static_cast<double>(ns) / 1'000'000.0;
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    std::mutex mutex;
    std::array<Slot, MaxTrackedThreads> slots{};
    u64 overflow_submits{};
    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace VideoCore
