// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <limits>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1WakerStageKProfiler final {
public:
    enum class GrandparentStatus : u32 {
        Valid = 0,
        ParentUnavailable = 1,
        InvalidParentFpRange = 2,
        ZeroParentFp = 3,
        BadParentFp = 4,
        InvalidGrandparentRange = 5,
        ZeroGrandparent = 6,
        Count = 7,
    };

    static X1WakerStageKProfiler& Get() {
        static X1WakerStageKProfiler profiler;
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

    void RecordCpuSlice(u32 producer_index, u64 thread_id, u64 pc, u64 lr, u64 parent_lr,
                        u64 grandparent_lr, GrandparentStatus grandparent_status,
                        s64 cpu_ticks) noexcept {
        if (!Enabled() || producer_index >= ProducerCount || thread_id == 0) {
            return;
        }

        auto& producer = producers[producer_index];
        const u64 previous = producer.thread_id.exchange(thread_id, std::memory_order_acq_rel);
        if (previous != 0 && previous != thread_id) {
            producer.identity_switches.fetch_add(1, std::memory_order_relaxed);
        }

        if (cpu_ticks < 0) {
            producer.malformed_ticks.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        const u64 ticks = static_cast<u64>(cpu_ticks);
        producer.slice_count.fetch_add(1, std::memory_order_relaxed);
        producer.total_ticks.fetch_add(ticks, std::memory_order_relaxed);

        const u32 status = static_cast<u32>(grandparent_status);
        if (status >= GrandparentStatusCount) {
            producer.bad_status.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        producer.status_slices[status].fetch_add(1, std::memory_order_relaxed);
        producer.status_ticks[status].fetch_add(ticks, std::memory_order_relaxed);

        if (grandparent_status != GrandparentStatus::Valid || grandparent_lr == 0 || pc == 0) {
            return;
        }

        const u32 slot = FindOrClaimContext(producer, pc, lr, parent_lr, grandparent_lr);
        if (slot == InvalidSlot) {
            producer.overflow_slices.fetch_add(1, std::memory_order_relaxed);
            producer.overflow_ticks.fetch_add(ticks, std::memory_order_relaxed);
            return;
        }
        producer.contexts[slot].slices.fetch_add(1, std::memory_order_relaxed);
        producer.contexts[slot].ticks.fetch_add(ticks, std::memory_order_relaxed);
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
                "[X1-WAKERK] frame={} frames={} producer={} tid={:#x} slices={} cpuTicks={} "
                "validN={} validTicks={} parentUnavailableN={} parentUnavailableTicks={} "
                "parentRangeBadN={} parentRangeBadTicks={} parentFpZeroN={} parentFpZeroTicks={} "
                "parentFpBadN={} parentFpBadTicks={} grandRangeBadN={} grandRangeBadTicks={} "
                "grandZeroN={} grandZeroTicks={} overflowN={} overflowTicks={} "
                "identitySwitch={} malTicks={} badStatus={} "
                "top0={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "top1={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "top2={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "top3={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}%",
                frame, frames, producer_index, snapshot.thread_id, snapshot.slice_count,
                snapshot.total_ticks, snapshot.status_slices[0], snapshot.status_ticks[0],
                snapshot.status_slices[1], snapshot.status_ticks[1], snapshot.status_slices[2],
                snapshot.status_ticks[2], snapshot.status_slices[3], snapshot.status_ticks[3],
                snapshot.status_slices[4], snapshot.status_ticks[4], snapshot.status_slices[5],
                snapshot.status_ticks[5], snapshot.status_slices[6], snapshot.status_ticks[6],
                snapshot.overflow_slices, snapshot.overflow_ticks, snapshot.identity_switches,
                snapshot.malformed_ticks, snapshot.bad_status, top0.pc, top0.lr, top0.parent_lr,
                top0.grandparent_lr, top0.ticks, top0.slices, Share(top0.ticks, snapshot.total_ticks),
                top1.pc, top1.lr, top1.parent_lr, top1.grandparent_lr, top1.ticks, top1.slices,
                Share(top1.ticks, snapshot.total_ticks), top2.pc, top2.lr, top2.parent_lr,
                top2.grandparent_lr, top2.ticks, top2.slices, Share(top2.ticks, snapshot.total_ticks),
                top3.pc, top3.lr, top3.parent_lr, top3.grandparent_lr, top3.ticks, top3.slices,
                Share(top3.ticks, snapshot.total_ticks));
        }
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ProducerCount = 2;
    static constexpr size_t ContextSlotCount = 64;
    static constexpr size_t ReportTopCount = 4;
    static constexpr size_t GrandparentStatusCount = static_cast<size_t>(GrandparentStatus::Count);
    static constexpr u64 ClaimingPc = (std::numeric_limits<u64>::max)();
    static constexpr u32 InvalidSlot = (std::numeric_limits<u32>::max)();

    struct ContextSlot {
        std::atomic<u64> pc{0};
        std::atomic<u64> lr{0};
        std::atomic<u64> parent_lr{0};
        std::atomic<u64> grandparent_lr{0};
        std::atomic<u64> slices{0};
        std::atomic<u64> ticks{0};
    };

    struct ContextSnapshot {
        u64 pc{};
        u64 lr{};
        u64 parent_lr{};
        u64 grandparent_lr{};
        u64 slices{};
        u64 ticks{};
    };

    struct ProducerState {
        std::atomic<u64> thread_id{0};
        std::atomic<u64> slice_count{0};
        std::atomic<u64> total_ticks{0};
        std::array<std::atomic<u64>, GrandparentStatusCount> status_slices{};
        std::array<std::atomic<u64>, GrandparentStatusCount> status_ticks{};
        std::atomic<u64> overflow_slices{0};
        std::atomic<u64> overflow_ticks{0};
        std::atomic<u64> identity_switches{0};
        std::atomic<u64> malformed_ticks{0};
        std::atomic<u64> bad_status{0};
        std::array<ContextSlot, ContextSlotCount> contexts{};
    };

    struct ProducerSnapshot {
        u64 thread_id{};
        u64 slice_count{};
        u64 total_ticks{};
        std::array<u64, GrandparentStatusCount> status_slices{};
        std::array<u64, GrandparentStatusCount> status_ticks{};
        u64 overflow_slices{};
        u64 overflow_ticks{};
        u64 identity_switches{};
        u64 malformed_ticks{};
        u64 bad_status{};
        std::array<ContextSnapshot, ReportTopCount> top{};
    };

    X1WakerStageKProfiler() = default;

    static double Share(u64 ticks, u64 total_ticks) noexcept {
        return total_ticks == 0 ? 0.0
                                : static_cast<double>(ticks) * 100.0 /
                                      static_cast<double>(total_ticks);
    }

    static u32 FindOrClaimContext(ProducerState& producer, u64 pc, u64 lr, u64 parent_lr,
                                  u64 grandparent_lr) noexcept {
        for (u32 i = 0; i < ContextSlotCount; ++i) {
            auto& slot = producer.contexts[i];
            const u64 slot_pc = slot.pc.load(std::memory_order_acquire);
            if (slot_pc == pc && slot.lr.load(std::memory_order_relaxed) == lr &&
                slot.parent_lr.load(std::memory_order_relaxed) == parent_lr &&
                slot.grandparent_lr.load(std::memory_order_relaxed) == grandparent_lr) {
                return i;
            }
            if (slot_pc != 0) {
                continue;
            }
            u64 expected = 0;
            if (slot.pc.compare_exchange_strong(expected, ClaimingPc, std::memory_order_acq_rel,
                                                std::memory_order_relaxed)) {
                slot.lr.store(lr, std::memory_order_relaxed);
                slot.parent_lr.store(parent_lr, std::memory_order_relaxed);
                slot.grandparent_lr.store(grandparent_lr, std::memory_order_relaxed);
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
        for (size_t i = 0; i < GrandparentStatusCount; ++i) {
            snapshot.status_slices[i] = producer.status_slices[i].exchange(0, std::memory_order_relaxed);
            snapshot.status_ticks[i] = producer.status_ticks[i].exchange(0, std::memory_order_relaxed);
        }
        snapshot.overflow_slices = producer.overflow_slices.exchange(0, std::memory_order_relaxed);
        snapshot.overflow_ticks = producer.overflow_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.identity_switches = producer.identity_switches.exchange(0, std::memory_order_relaxed);
        snapshot.malformed_ticks = producer.malformed_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.bad_status = producer.bad_status.exchange(0, std::memory_order_relaxed);
        for (auto& slot : producer.contexts) {
            const u64 pc = slot.pc.load(std::memory_order_acquire);
            if (pc == 0 || pc == ClaimingPc) {
                continue;
            }
            ContextSnapshot context{};
            context.pc = pc;
            context.lr = slot.lr.load(std::memory_order_relaxed);
            context.parent_lr = slot.parent_lr.load(std::memory_order_relaxed);
            context.grandparent_lr = slot.grandparent_lr.load(std::memory_order_relaxed);
            context.slices = slot.slices.exchange(0, std::memory_order_relaxed);
            context.ticks = slot.ticks.exchange(0, std::memory_order_relaxed);
            InsertTop(snapshot.top, context);
        }
        return snapshot;
    }

    static void ResetProducerAll(ProducerState& producer) noexcept {
        producer.thread_id.store(0, std::memory_order_relaxed);
        producer.slice_count.store(0, std::memory_order_relaxed);
        producer.total_ticks.store(0, std::memory_order_relaxed);
        for (size_t i = 0; i < GrandparentStatusCount; ++i) {
            producer.status_slices[i].store(0, std::memory_order_relaxed);
            producer.status_ticks[i].store(0, std::memory_order_relaxed);
        }
        producer.overflow_slices.store(0, std::memory_order_relaxed);
        producer.overflow_ticks.store(0, std::memory_order_relaxed);
        producer.identity_switches.store(0, std::memory_order_relaxed);
        producer.malformed_ticks.store(0, std::memory_order_relaxed);
        producer.bad_status.store(0, std::memory_order_relaxed);
        for (auto& slot : producer.contexts) {
            slot.pc.store(0, std::memory_order_relaxed);
            slot.lr.store(0, std::memory_order_relaxed);
            slot.parent_lr.store(0, std::memory_order_relaxed);
            slot.grandparent_lr.store(0, std::memory_order_relaxed);
            slot.slices.store(0, std::memory_order_relaxed);
            slot.ticks.store(0, std::memory_order_relaxed);
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    std::array<ProducerState, ProducerCount> producers{};
};

} // namespace Core
