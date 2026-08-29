// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <limits>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1WakerStageGProfiler final {
public:
    using Clock = std::chrono::steady_clock;

    static X1WakerStageGProfiler& Get() {
        static X1WakerStageGProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_address_arbiter_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;
        for (auto& producer : producers) {
            ResetProducerAll(producer);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void RecordScheduledIn(u32 producer_index, u64 thread_id, u64 clock_ticks, s32 priority,
                           s32 active_core, s32 current_core) noexcept {
        if (!Enabled() || producer_index >= ProducerCount || thread_id == 0) {
            return;
        }

        auto& producer = producers[producer_index];
        NoteIdentity(producer, thread_id);
        producer.latest_priority.store(priority, std::memory_order_relaxed);
        producer.latest_active_core.store(active_core, std::memory_order_relaxed);
        producer.latest_current_core.store(current_core, std::memory_order_relaxed);

        const u64 now_ns = NowNs();
        const u64 previous_start = producer.slice_start_ns.exchange(now_ns, std::memory_order_acq_rel);
        producer.slice_start_clock.store(clock_ticks, std::memory_order_release);
        if (previous_start != 0) {
            producer.malformed_starts.fetch_add(1, std::memory_order_relaxed);
        }
    }

    void RecordCpuSlice(u32 producer_index, u64 thread_id, u64 pc, u64 lr, s64 cpu_ticks,
                        u64 clock_ticks, s32 priority, s32 active_core,
                        s32 current_core) noexcept {
        if (!Enabled() || producer_index >= ProducerCount || thread_id == 0) {
            return;
        }

        auto& producer = producers[producer_index];
        NoteIdentity(producer, thread_id);
        producer.latest_priority.store(priority, std::memory_order_relaxed);
        producer.latest_active_core.store(active_core, std::memory_order_relaxed);
        producer.latest_current_core.store(current_core, std::memory_order_relaxed);

        if (cpu_ticks < 0) {
            producer.malformed_ticks.fetch_add(1, std::memory_order_relaxed);
            producer.slice_start_ns.store(0, std::memory_order_relaxed);
            producer.slice_start_clock.store(0, std::memory_order_relaxed);
            return;
        }

        const u64 ticks = static_cast<u64>(cpu_ticks);
        const u64 now_ns = NowNs();
        const u64 start_ns = producer.slice_start_ns.exchange(0, std::memory_order_acq_rel);
        const u64 start_clock = producer.slice_start_clock.exchange(0, std::memory_order_acq_rel);

        u64 wall_ns = 0;
        if (start_ns == 0 || now_ns < start_ns) {
            producer.missing_starts.fetch_add(1, std::memory_order_relaxed);
        } else {
            wall_ns = now_ns - start_ns;
        }

        if (start_clock != 0) {
            if (clock_ticks < start_clock || clock_ticks - start_clock != ticks) {
                producer.clock_mismatch.fetch_add(1, std::memory_order_relaxed);
            }
        }

        producer.slice_count.fetch_add(1, std::memory_order_relaxed);
        producer.total_ticks.fetch_add(ticks, std::memory_order_relaxed);
        producer.total_wall_ns.fetch_add(wall_ns, std::memory_order_relaxed);

        if (pc == 0) {
            producer.unknown_slices.fetch_add(1, std::memory_order_relaxed);
            producer.unknown_ticks.fetch_add(ticks, std::memory_order_relaxed);
            producer.unknown_wall_ns.fetch_add(wall_ns, std::memory_order_relaxed);
            return;
        }

        const u32 slot = FindOrClaimContext(producer, pc, lr);
        if (slot == InvalidSlot) {
            producer.overflow_slices.fetch_add(1, std::memory_order_relaxed);
            producer.overflow_ticks.fetch_add(ticks, std::memory_order_relaxed);
            producer.overflow_wall_ns.fetch_add(wall_ns, std::memory_order_relaxed);
            return;
        }

        producer.contexts[slot].slices.fetch_add(1, std::memory_order_relaxed);
        producer.contexts[slot].ticks.fetch_add(ticks, std::memory_order_relaxed);
        producer.contexts[slot].wall_ns.fetch_add(wall_ns, std::memory_order_relaxed);
    }

    void FrameEnd() noexcept {
        if (!Enabled()) {
            return;
        }

        const u64 frame = frame_id.fetch_add(1, std::memory_order_relaxed) + 1;
        ++frames_since_report;
        if (frames_since_report < ReportFrames) {
            return;
        }
        const u64 frames = frames_since_report;
        frames_since_report = 0;

        for (size_t producer_index = 0; producer_index < ProducerCount; ++producer_index) {
            const auto snapshot = SnapshotAndResetWindow(producers[producer_index]);
            const auto& top0 = snapshot.top[0];
            const auto& top1 = snapshot.top[1];
            const auto& top2 = snapshot.top[2];
            const auto& top3 = snapshot.top[3];

            LOG_INFO(
                HW_GPU,
                "[X1-WAKERG] frame={} frames={} producer={} tid={:#x} slices={} cpuTicks={} "
                "cpuWall={:.3f}ms unknownN={} unknownTicks={} unknownWall={:.3f}ms "
                "overflowN={} overflowTicks={} overflowWall={:.3f}ms identitySwitch={} "
                "missingStart={} malStart={} malTicks={} clockMismatch={} prio={} activeCore={} "
                "currentCore={} "
                "top0={:#x}/{:#x}/{}/{:.3f}ms/{}/{:.2f}% "
                "top1={:#x}/{:#x}/{}/{:.3f}ms/{}/{:.2f}% "
                "top2={:#x}/{:#x}/{}/{:.3f}ms/{}/{:.2f}% "
                "top3={:#x}/{:#x}/{}/{:.3f}ms/{}/{:.2f}%",
                frame, frames, producer_index, snapshot.thread_id, snapshot.slice_count,
                snapshot.total_ticks, ToMs(snapshot.total_wall_ns), snapshot.unknown_slices,
                snapshot.unknown_ticks, ToMs(snapshot.unknown_wall_ns), snapshot.overflow_slices,
                snapshot.overflow_ticks, ToMs(snapshot.overflow_wall_ns),
                snapshot.identity_switches, snapshot.missing_starts, snapshot.malformed_starts,
                snapshot.malformed_ticks, snapshot.clock_mismatch, snapshot.priority,
                snapshot.active_core, snapshot.current_core, top0.pc, top0.lr, top0.ticks,
                ToMs(top0.wall_ns), top0.slices, Share(top0.ticks, snapshot.total_ticks), top1.pc,
                top1.lr, top1.ticks, ToMs(top1.wall_ns), top1.slices,
                Share(top1.ticks, snapshot.total_ticks), top2.pc, top2.lr, top2.ticks,
                ToMs(top2.wall_ns), top2.slices, Share(top2.ticks, snapshot.total_ticks), top3.pc,
                top3.lr, top3.ticks, ToMs(top3.wall_ns), top3.slices,
                Share(top3.ticks, snapshot.total_ticks));
        }
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ProducerCount = 2;
    static constexpr size_t ContextSlotCount = 64;
    static constexpr size_t ReportTopCount = 4;
    static constexpr u64 ClaimingPc = (std::numeric_limits<u64>::max)();
    static constexpr u32 InvalidSlot = (std::numeric_limits<u32>::max)();

    struct ContextSlot {
        std::atomic<u64> pc{0};
        std::atomic<u64> lr{0};
        std::atomic<u64> slices{0};
        std::atomic<u64> ticks{0};
        std::atomic<u64> wall_ns{0};
    };

    struct ContextSnapshot {
        u64 pc{};
        u64 lr{};
        u64 slices{};
        u64 ticks{};
        u64 wall_ns{};
    };

    struct ProducerState {
        std::atomic<u64> thread_id{0};
        std::atomic<u64> slice_count{0};
        std::atomic<u64> total_ticks{0};
        std::atomic<u64> total_wall_ns{0};
        std::atomic<u64> unknown_slices{0};
        std::atomic<u64> unknown_ticks{0};
        std::atomic<u64> unknown_wall_ns{0};
        std::atomic<u64> overflow_slices{0};
        std::atomic<u64> overflow_ticks{0};
        std::atomic<u64> overflow_wall_ns{0};
        std::atomic<u64> identity_switches{0};
        std::atomic<u64> missing_starts{0};
        std::atomic<u64> malformed_starts{0};
        std::atomic<u64> malformed_ticks{0};
        std::atomic<u64> clock_mismatch{0};
        std::atomic<u64> slice_start_ns{0};
        std::atomic<u64> slice_start_clock{0};
        std::atomic<s32> latest_priority{0};
        std::atomic<s32> latest_active_core{-1};
        std::atomic<s32> latest_current_core{-1};
        std::array<ContextSlot, ContextSlotCount> contexts{};
    };

    struct ProducerSnapshot {
        u64 thread_id{};
        u64 slice_count{};
        u64 total_ticks{};
        u64 total_wall_ns{};
        u64 unknown_slices{};
        u64 unknown_ticks{};
        u64 unknown_wall_ns{};
        u64 overflow_slices{};
        u64 overflow_ticks{};
        u64 overflow_wall_ns{};
        u64 identity_switches{};
        u64 missing_starts{};
        u64 malformed_starts{};
        u64 malformed_ticks{};
        u64 clock_mismatch{};
        s32 priority{};
        s32 active_core{-1};
        s32 current_core{-1};
        std::array<ContextSnapshot, ReportTopCount> top{};
    };

    X1WakerStageGProfiler() = default;

    static u64 NowNs() noexcept {
        return static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch())
                .count());
    }

    static double ToMs(u64 ns) noexcept {
        return static_cast<double>(ns) / 1'000'000.0;
    }

    static double Share(u64 ticks, u64 total_ticks) noexcept {
        if (total_ticks == 0) {
            return 0.0;
        }
        return static_cast<double>(ticks) * 100.0 / static_cast<double>(total_ticks);
    }

    static void NoteIdentity(ProducerState& producer, u64 thread_id) noexcept {
        const u64 previous = producer.thread_id.exchange(thread_id, std::memory_order_acq_rel);
        if (previous != 0 && previous != thread_id) {
            producer.identity_switches.fetch_add(1, std::memory_order_relaxed);
            producer.slice_start_ns.store(0, std::memory_order_relaxed);
            producer.slice_start_clock.store(0, std::memory_order_relaxed);
        }
    }

    static u32 FindOrClaimContext(ProducerState& producer, u64 pc, u64 lr) noexcept {
        for (u32 i = 0; i < ContextSlotCount; ++i) {
            auto& slot = producer.contexts[i];
            const u64 slot_pc = slot.pc.load(std::memory_order_acquire);
            if (slot_pc == pc && slot.lr.load(std::memory_order_relaxed) == lr) {
                return i;
            }
            if (slot_pc != 0) {
                continue;
            }

            u64 expected = 0;
            if (slot.pc.compare_exchange_strong(expected, ClaimingPc, std::memory_order_acq_rel,
                                                std::memory_order_relaxed)) {
                slot.lr.store(lr, std::memory_order_relaxed);
                slot.pc.store(pc, std::memory_order_release);
                return i;
            }
        }
        return InvalidSlot;
    }

    static void InsertTop(std::array<ContextSnapshot, ReportTopCount>& top,
                          const ContextSnapshot& candidate) noexcept {
        if (candidate.ticks == 0) {
            return;
        }
        for (size_t i = 0; i < ReportTopCount; ++i) {
            if (candidate.ticks <= top[i].ticks) {
                continue;
            }
            for (size_t j = ReportTopCount - 1; j > i; --j) {
                top[j] = top[j - 1];
            }
            top[i] = candidate;
            return;
        }
    }

    static ProducerSnapshot SnapshotAndResetWindow(ProducerState& producer) noexcept {
        ProducerSnapshot snapshot{};
        snapshot.thread_id = producer.thread_id.load(std::memory_order_relaxed);
        snapshot.slice_count = producer.slice_count.exchange(0, std::memory_order_relaxed);
        snapshot.total_ticks = producer.total_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.total_wall_ns = producer.total_wall_ns.exchange(0, std::memory_order_relaxed);
        snapshot.unknown_slices = producer.unknown_slices.exchange(0, std::memory_order_relaxed);
        snapshot.unknown_ticks = producer.unknown_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.unknown_wall_ns =
            producer.unknown_wall_ns.exchange(0, std::memory_order_relaxed);
        snapshot.overflow_slices = producer.overflow_slices.exchange(0, std::memory_order_relaxed);
        snapshot.overflow_ticks = producer.overflow_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.overflow_wall_ns =
            producer.overflow_wall_ns.exchange(0, std::memory_order_relaxed);
        snapshot.identity_switches =
            producer.identity_switches.exchange(0, std::memory_order_relaxed);
        snapshot.missing_starts = producer.missing_starts.exchange(0, std::memory_order_relaxed);
        snapshot.malformed_starts =
            producer.malformed_starts.exchange(0, std::memory_order_relaxed);
        snapshot.malformed_ticks = producer.malformed_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.clock_mismatch = producer.clock_mismatch.exchange(0, std::memory_order_relaxed);
        snapshot.priority = producer.latest_priority.load(std::memory_order_relaxed);
        snapshot.active_core = producer.latest_active_core.load(std::memory_order_relaxed);
        snapshot.current_core = producer.latest_current_core.load(std::memory_order_relaxed);

        for (auto& slot : producer.contexts) {
            const u64 pc = slot.pc.load(std::memory_order_acquire);
            if (pc == 0 || pc == ClaimingPc) {
                continue;
            }
            ContextSnapshot context{};
            context.pc = pc;
            context.lr = slot.lr.load(std::memory_order_relaxed);
            context.slices = slot.slices.exchange(0, std::memory_order_relaxed);
            context.ticks = slot.ticks.exchange(0, std::memory_order_relaxed);
            context.wall_ns = slot.wall_ns.exchange(0, std::memory_order_relaxed);
            InsertTop(snapshot.top, context);
        }
        return snapshot;
    }

    static void ResetProducerAll(ProducerState& producer) noexcept {
        producer.thread_id.store(0, std::memory_order_relaxed);
        producer.slice_count.store(0, std::memory_order_relaxed);
        producer.total_ticks.store(0, std::memory_order_relaxed);
        producer.total_wall_ns.store(0, std::memory_order_relaxed);
        producer.unknown_slices.store(0, std::memory_order_relaxed);
        producer.unknown_ticks.store(0, std::memory_order_relaxed);
        producer.unknown_wall_ns.store(0, std::memory_order_relaxed);
        producer.overflow_slices.store(0, std::memory_order_relaxed);
        producer.overflow_ticks.store(0, std::memory_order_relaxed);
        producer.overflow_wall_ns.store(0, std::memory_order_relaxed);
        producer.identity_switches.store(0, std::memory_order_relaxed);
        producer.missing_starts.store(0, std::memory_order_relaxed);
        producer.malformed_starts.store(0, std::memory_order_relaxed);
        producer.malformed_ticks.store(0, std::memory_order_relaxed);
        producer.clock_mismatch.store(0, std::memory_order_relaxed);
        producer.slice_start_ns.store(0, std::memory_order_relaxed);
        producer.slice_start_clock.store(0, std::memory_order_relaxed);
        producer.latest_priority.store(0, std::memory_order_relaxed);
        producer.latest_active_core.store(-1, std::memory_order_relaxed);
        producer.latest_current_core.store(-1, std::memory_order_relaxed);
        for (auto& slot : producer.contexts) {
            slot.pc.store(0, std::memory_order_relaxed);
            slot.lr.store(0, std::memory_order_relaxed);
            slot.slices.store(0, std::memory_order_relaxed);
            slot.ticks.store(0, std::memory_order_relaxed);
            slot.wall_ns.store(0, std::memory_order_relaxed);
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    std::array<ProducerState, ProducerCount> producers{};
};

} // namespace Core
