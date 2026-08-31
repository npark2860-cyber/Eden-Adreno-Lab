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

    enum class WorkTargetStatus : u32 {
        Valid = 0,
        MainRangeUnavailable = 1,
        ZeroNode = 2,
        BadNode = 3,
        InvalidNodeRange = 4,
        ZeroWorkObject = 5,
        BadWorkObject = 6,
        InvalidWorkObjectRange = 7,
        ZeroVtable = 8,
        BadVtable = 9,
        InvalidShimRange = 10,
        InvalidWorkTargetRange = 11,
        ZeroResolvedTarget = 12,
        TargetOutsideMain = 13,
        Count = 14,
    };

    static X1WakerStageKProfiler& Get() {
        static X1WakerStageKProfiler profiler;
        return profiler;
    }

    void RegisterMainModuleRange(u64 base, u64 end) noexcept {
        if (base == 0 || end <= base) {
            return;
        }
        main_end.store(end, std::memory_order_relaxed);
        main_base.store(base, std::memory_order_release);
    }

    [[nodiscard]] bool HasMainModuleRange() const noexcept {
        const u64 base = main_base.load(std::memory_order_acquire);
        const u64 end = main_end.load(std::memory_order_relaxed);
        return base != 0 && end > base;
    }

    [[nodiscard]] bool NormalizeMainTarget(u64 target, u64& offset) const noexcept {
        const u64 base = main_base.load(std::memory_order_acquire);
        const u64 end = main_end.load(std::memory_order_relaxed);
        if (base == 0 || end <= base || target < base || target >= end) {
            return false;
        }
        offset = target - base;
        return true;
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
                        u64 shim_offset, u64 work_offset, WorkTargetStatus work_status,
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

        const u32 work_status_index = static_cast<u32>(work_status);
        if (work_status_index >= WorkTargetStatusCount) {
            producer.work_bad_status.fetch_add(1, std::memory_order_relaxed);
        } else {
            producer.work_status_slices[work_status_index].fetch_add(1, std::memory_order_relaxed);
            producer.work_status_ticks[work_status_index].fetch_add(ticks, std::memory_order_relaxed);
            if (work_status == WorkTargetStatus::Valid) {
                producer.work_resolved_slices.fetch_add(1, std::memory_order_relaxed);
                producer.work_resolved_ticks.fetch_add(ticks, std::memory_order_relaxed);
                const u32 work_slot = FindOrClaimWorkPair(producer, shim_offset, work_offset);
                if (work_slot == InvalidSlot) {
                    producer.work_overflow_slices.fetch_add(1, std::memory_order_relaxed);
                    producer.work_overflow_ticks.fetch_add(ticks, std::memory_order_relaxed);
                } else {
                    producer.work_pairs[work_slot].slices.fetch_add(1, std::memory_order_relaxed);
                    producer.work_pairs[work_slot].ticks.fetch_add(ticks, std::memory_order_relaxed);
                }
            }
        }

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
            const auto& work_top0 = snapshot.work_top[0];
            const auto& work_top1 = snapshot.work_top[1];
            const auto& work_top2 = snapshot.work_top[2];
            const auto& work_top3 = snapshot.work_top[3];
            const u64 work_reported_ticks = work_top0.ticks + work_top1.ticks + work_top2.ticks +
                                            work_top3.ticks;
            const u64 work_other_resolved_ticks =
                snapshot.work_resolved_ticks >= work_reported_ticks
                    ? snapshot.work_resolved_ticks - work_reported_ticks
                    : 0;
            LOG_INFO(
                HW_GPU,
                "[X1-WAKERK] frame={} frames={} producer={} tid={:#x} slices={} cpuTicks={} "
                "validN={} validTicks={} parentUnavailableN={} parentUnavailableTicks={} "
                "parentRangeBadN={} parentRangeBadTicks={} parentFpZeroN={} parentFpZeroTicks={} "
                "parentFpBadN={} parentFpBadTicks={} grandRangeBadN={} grandRangeBadTicks={} "
                "grandZeroN={} grandZeroTicks={} overflowN={} overflowTicks={} "
                "identitySwitch={} malTicks={} badStatus={} "
                "workResolvedN={} workResolvedTicks={} workOtherResolvedTicks={} "
                "workOverflowN={} workOverflowTicks={} workBadStatus={} "
                "workMainUnavailableN={} workMainUnavailableTicks={} "
                "workNodeZeroN={} workNodeZeroTicks={} workNodeBadN={} workNodeBadTicks={} "
                "workNodeRangeBadN={} workNodeRangeBadTicks={} "
                "workObjectZeroN={} workObjectZeroTicks={} workObjectBadN={} workObjectBadTicks={} "
                "workObjectRangeBadN={} workObjectRangeBadTicks={} "
                "workVtableZeroN={} workVtableZeroTicks={} workVtableBadN={} workVtableBadTicks={} "
                "workShimRangeBadN={} workShimRangeBadTicks={} "
                "workTargetRangeBadN={} workTargetRangeBadTicks={} "
                "workTargetZeroN={} workTargetZeroTicks={} "
                "workOutsideMainN={} workOutsideMainTicks={} "
                "top0={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "top1={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "top2={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "top3={:#x}/{:#x}/{:#x}/{:#x}/{}/{}/{:.2f}% "
                "workTop0={:#x}/{:#x}/{}/{}/{:.2f}% "
                "workTop1={:#x}/{:#x}/{}/{}/{:.2f}% "
                "workTop2={:#x}/{:#x}/{}/{}/{:.2f}% "
                "workTop3={:#x}/{:#x}/{}/{}/{:.2f}%",
                frame, frames, producer_index, snapshot.thread_id, snapshot.slice_count,
                snapshot.total_ticks, snapshot.status_slices[0], snapshot.status_ticks[0],
                snapshot.status_slices[1], snapshot.status_ticks[1], snapshot.status_slices[2],
                snapshot.status_ticks[2], snapshot.status_slices[3], snapshot.status_ticks[3],
                snapshot.status_slices[4], snapshot.status_ticks[4], snapshot.status_slices[5],
                snapshot.status_ticks[5], snapshot.status_slices[6], snapshot.status_ticks[6],
                snapshot.overflow_slices, snapshot.overflow_ticks, snapshot.identity_switches,
                snapshot.malformed_ticks, snapshot.bad_status, snapshot.work_resolved_slices,
                snapshot.work_resolved_ticks, work_other_resolved_ticks,
                snapshot.work_overflow_slices, snapshot.work_overflow_ticks,
                snapshot.work_bad_status, snapshot.work_status_slices[1],
                snapshot.work_status_ticks[1], snapshot.work_status_slices[2],
                snapshot.work_status_ticks[2], snapshot.work_status_slices[3],
                snapshot.work_status_ticks[3], snapshot.work_status_slices[4],
                snapshot.work_status_ticks[4], snapshot.work_status_slices[5],
                snapshot.work_status_ticks[5], snapshot.work_status_slices[6],
                snapshot.work_status_ticks[6], snapshot.work_status_slices[7],
                snapshot.work_status_ticks[7], snapshot.work_status_slices[8],
                snapshot.work_status_ticks[8], snapshot.work_status_slices[9],
                snapshot.work_status_ticks[9], snapshot.work_status_slices[10],
                snapshot.work_status_ticks[10], snapshot.work_status_slices[11],
                snapshot.work_status_ticks[11], snapshot.work_status_slices[12],
                snapshot.work_status_ticks[12], snapshot.work_status_slices[13],
                snapshot.work_status_ticks[13], top0.pc, top0.lr, top0.parent_lr,
                top0.grandparent_lr, top0.ticks, top0.slices,
                Share(top0.ticks, snapshot.total_ticks), top1.pc, top1.lr, top1.parent_lr,
                top1.grandparent_lr, top1.ticks, top1.slices,
                Share(top1.ticks, snapshot.total_ticks), top2.pc, top2.lr, top2.parent_lr,
                top2.grandparent_lr, top2.ticks, top2.slices,
                Share(top2.ticks, snapshot.total_ticks), top3.pc, top3.lr, top3.parent_lr,
                top3.grandparent_lr, top3.ticks, top3.slices,
                Share(top3.ticks, snapshot.total_ticks), work_top0.shim_offset,
                work_top0.work_offset, work_top0.ticks, work_top0.slices,
                Share(work_top0.ticks, snapshot.total_ticks), work_top1.shim_offset,
                work_top1.work_offset, work_top1.ticks, work_top1.slices,
                Share(work_top1.ticks, snapshot.total_ticks), work_top2.shim_offset,
                work_top2.work_offset, work_top2.ticks, work_top2.slices,
                Share(work_top2.ticks, snapshot.total_ticks), work_top3.shim_offset,
                work_top3.work_offset, work_top3.ticks, work_top3.slices,
                Share(work_top3.ticks, snapshot.total_ticks));
        }
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ProducerCount = 2;
    static constexpr size_t ContextSlotCount = 64;
    static constexpr size_t WorkPairSlotCount = 64;
    static constexpr size_t ReportTopCount = 4;
    static constexpr size_t GrandparentStatusCount = static_cast<size_t>(GrandparentStatus::Count);
    static constexpr size_t WorkTargetStatusCount = static_cast<size_t>(WorkTargetStatus::Count);
    static constexpr u64 ClaimingPc = (std::numeric_limits<u64>::max)();
    static constexpr u64 EmptyWorkShim = (std::numeric_limits<u64>::max)() - 1;
    static constexpr u64 ClaimingWorkShim = (std::numeric_limits<u64>::max)();
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

    struct WorkPairSlot {
        std::atomic<u64> shim_offset{EmptyWorkShim};
        std::atomic<u64> work_offset{0};
        std::atomic<u64> slices{0};
        std::atomic<u64> ticks{0};
    };

    struct WorkPairSnapshot {
        u64 shim_offset{};
        u64 work_offset{};
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
        std::array<std::atomic<u64>, WorkTargetStatusCount> work_status_slices{};
        std::array<std::atomic<u64>, WorkTargetStatusCount> work_status_ticks{};
        std::atomic<u64> work_resolved_slices{0};
        std::atomic<u64> work_resolved_ticks{0};
        std::atomic<u64> work_overflow_slices{0};
        std::atomic<u64> work_overflow_ticks{0};
        std::atomic<u64> work_bad_status{0};
        std::array<WorkPairSlot, WorkPairSlotCount> work_pairs{};
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
        std::array<u64, WorkTargetStatusCount> work_status_slices{};
        std::array<u64, WorkTargetStatusCount> work_status_ticks{};
        u64 work_resolved_slices{};
        u64 work_resolved_ticks{};
        u64 work_overflow_slices{};
        u64 work_overflow_ticks{};
        u64 work_bad_status{};
        std::array<WorkPairSnapshot, ReportTopCount> work_top{};
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

    static u32 FindOrClaimWorkPair(ProducerState& producer, u64 shim_offset,
                                   u64 work_offset) noexcept {
        for (u32 i = 0; i < WorkPairSlotCount; ++i) {
            auto& slot = producer.work_pairs[i];
            const u64 slot_shim = slot.shim_offset.load(std::memory_order_acquire);
            if (slot_shim == shim_offset &&
                slot.work_offset.load(std::memory_order_relaxed) == work_offset) {
                return i;
            }
            if (slot_shim != EmptyWorkShim) {
                continue;
            }
            u64 expected = EmptyWorkShim;
            if (slot.shim_offset.compare_exchange_strong(expected, ClaimingWorkShim,
                                                         std::memory_order_acq_rel,
                                                         std::memory_order_relaxed)) {
                slot.work_offset.store(work_offset, std::memory_order_relaxed);
                slot.shim_offset.store(shim_offset, std::memory_order_release);
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

    static void InsertWorkTop(std::array<WorkPairSnapshot, ReportTopCount>& top,
                              const WorkPairSnapshot& candidate) noexcept {
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
            snapshot.status_slices[i] =
                producer.status_slices[i].exchange(0, std::memory_order_relaxed);
            snapshot.status_ticks[i] =
                producer.status_ticks[i].exchange(0, std::memory_order_relaxed);
        }
        snapshot.overflow_slices = producer.overflow_slices.exchange(0, std::memory_order_relaxed);
        snapshot.overflow_ticks = producer.overflow_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.identity_switches =
            producer.identity_switches.exchange(0, std::memory_order_relaxed);
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
        for (size_t i = 0; i < WorkTargetStatusCount; ++i) {
            snapshot.work_status_slices[i] =
                producer.work_status_slices[i].exchange(0, std::memory_order_relaxed);
            snapshot.work_status_ticks[i] =
                producer.work_status_ticks[i].exchange(0, std::memory_order_relaxed);
        }
        snapshot.work_resolved_slices =
            producer.work_resolved_slices.exchange(0, std::memory_order_relaxed);
        snapshot.work_resolved_ticks =
            producer.work_resolved_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.work_overflow_slices =
            producer.work_overflow_slices.exchange(0, std::memory_order_relaxed);
        snapshot.work_overflow_ticks =
            producer.work_overflow_ticks.exchange(0, std::memory_order_relaxed);
        snapshot.work_bad_status =
            producer.work_bad_status.exchange(0, std::memory_order_relaxed);
        for (auto& slot : producer.work_pairs) {
            const u64 shim_offset = slot.shim_offset.load(std::memory_order_acquire);
            if (shim_offset == EmptyWorkShim || shim_offset == ClaimingWorkShim) {
                continue;
            }
            WorkPairSnapshot work{};
            work.shim_offset = shim_offset;
            work.work_offset = slot.work_offset.load(std::memory_order_relaxed);
            work.slices = slot.slices.exchange(0, std::memory_order_relaxed);
            work.ticks = slot.ticks.exchange(0, std::memory_order_relaxed);
            InsertWorkTop(snapshot.work_top, work);
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
        for (size_t i = 0; i < WorkTargetStatusCount; ++i) {
            producer.work_status_slices[i].store(0, std::memory_order_relaxed);
            producer.work_status_ticks[i].store(0, std::memory_order_relaxed);
        }
        producer.work_resolved_slices.store(0, std::memory_order_relaxed);
        producer.work_resolved_ticks.store(0, std::memory_order_relaxed);
        producer.work_overflow_slices.store(0, std::memory_order_relaxed);
        producer.work_overflow_ticks.store(0, std::memory_order_relaxed);
        producer.work_bad_status.store(0, std::memory_order_relaxed);
        for (auto& slot : producer.work_pairs) {
            slot.shim_offset.store(EmptyWorkShim, std::memory_order_relaxed);
            slot.work_offset.store(0, std::memory_order_relaxed);
            slot.slices.store(0, std::memory_order_relaxed);
            slot.ticks.store(0, std::memory_order_relaxed);
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    std::atomic<u64> main_base{0};
    std::atomic<u64> main_end{0};
    u64 frames_since_report{};
    std::array<ProducerState, ProducerCount> producers{};
};

} // namespace Core
