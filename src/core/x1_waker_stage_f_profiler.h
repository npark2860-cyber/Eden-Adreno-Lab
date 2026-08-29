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

class X1WakerStageFProfiler final {
public:
    using Clock = std::chrono::steady_clock;

    static X1WakerStageFProfiler& Get() {
        static X1WakerStageFProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_address_arbiter_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        tracked_address.store(0, std::memory_order_relaxed);
        tracking_switches.store(0, std::memory_order_relaxed);
        candidate_overflow.store(0, std::memory_order_relaxed);
        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;

        for (auto& slot : candidates) {
            slot.address.store(0, std::memory_order_relaxed);
            slot.thread_id.store(0, std::memory_order_relaxed);
            slot.calls.store(0, std::memory_order_relaxed);
        }
        for (auto& producer : producers) {
            ResetProducerAll(producer);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void RecordPromotedSignal(u64 thread_id, u64 address, u64 cpu_ticks, u64 clock_ticks,
                              s32 priority, s32 active_core, s32 current_core) noexcept {
        if (!Enabled() || thread_id == 0 || address == 0) {
            return;
        }

        const u32 candidate = FindOrClaimCandidate(address, thread_id);
        if (candidate == InvalidSlot) {
            candidate_overflow.fetch_add(1, std::memory_order_relaxed);
        } else {
            candidates[candidate].calls.fetch_add(1, std::memory_order_relaxed);
        }

        if (tracked_address.load(std::memory_order_acquire) != address) {
            return;
        }

        const u32 producer_index = FindTrackedProducer(thread_id);
        if (producer_index == InvalidSlot) {
            return;
        }

        auto& producer = producers[producer_index];
        producer.signal_calls.fetch_add(1, std::memory_order_relaxed);
        producer.latest_priority.store(priority, std::memory_order_relaxed);
        producer.latest_active_core.store(active_core, std::memory_order_relaxed);
        producer.latest_current_core.store(current_core, std::memory_order_relaxed);

        const u64 now_ns = NowNs();
        const u64 previous_ns = producer.previous_signal_ns.exchange(now_ns, std::memory_order_acq_rel);
        const u64 previous_cpu =
            producer.previous_cpu_ticks.exchange(cpu_ticks, std::memory_order_acq_rel);
        const u64 previous_clock =
            producer.previous_clock_ticks.exchange(clock_ticks, std::memory_order_acq_rel);

        if (previous_ns == 0) {
            producer.current_interval_wait_ns.store(0, std::memory_order_relaxed);
            return;
        }
        if (now_ns < previous_ns) {
            producer.malformed_intervals.fetch_add(1, std::memory_order_relaxed);
            producer.current_interval_wait_ns.store(0, std::memory_order_relaxed);
            return;
        }

        const u64 elapsed_ns = now_ns - previous_ns;
        const u64 interval_wait_ns =
            producer.current_interval_wait_ns.exchange(0, std::memory_order_acq_rel);
        if (interval_wait_ns > elapsed_ns) {
            producer.malformed_intervals.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        producer.interval_count.fetch_add(1, std::memory_order_relaxed);
        producer.inter_total_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
        AtomicMax(producer.inter_max_ns, elapsed_ns);
        producer.wait_total_ns.fetch_add(interval_wait_ns, std::memory_order_relaxed);

        const u64 residual_ns = elapsed_ns - interval_wait_ns;
        producer.residual_total_ns.fetch_add(residual_ns, std::memory_order_relaxed);

        u64 cpu_ns = 0;
        if (cpu_ticks >= previous_cpu && clock_ticks > previous_clock) {
            const u64 cpu_delta = cpu_ticks - previous_cpu;
            const u64 clock_delta = clock_ticks - previous_clock;
            cpu_ns = ScaleTicksToNs(cpu_delta, elapsed_ns, clock_delta);
            producer.cpu_total_ns.fetch_add(cpu_ns, std::memory_order_relaxed);
            AtomicMax(producer.cpu_max_ns, cpu_ns);
        } else {
            producer.malformed_cpu.fetch_add(1, std::memory_order_relaxed);
        }

        const u64 runnable_unscheduled_ns = residual_ns > cpu_ns ? residual_ns - cpu_ns : 0;
        if (cpu_ns > residual_ns) {
            producer.cpu_over_residual.fetch_add(1, std::memory_order_relaxed);
        }
        producer.runnable_unscheduled_total_ns.fetch_add(runnable_unscheduled_ns,
                                                         std::memory_order_relaxed);
        AtomicMax(producer.runnable_unscheduled_max_ns, runnable_unscheduled_ns);
    }

    void RecordThreadStateTransition(u64 thread_id, u32 old_state, u32 new_state,
                                     u32 old_wait_reason) noexcept {
        if (!Enabled()) {
            return;
        }
        const u32 producer_index = FindTrackedProducer(thread_id);
        if (producer_index == InvalidSlot) {
            return;
        }

        constexpr u32 Waiting = 1;
        auto& producer = producers[producer_index];
        const u64 now_ns = NowNs();

        if (old_state != Waiting && new_state == Waiting) {
            u64 expected = 0;
            if (!producer.wait_start_ns.compare_exchange_strong(
                    expected, now_ns, std::memory_order_acq_rel, std::memory_order_relaxed)) {
                producer.malformed_waits.fetch_add(1, std::memory_order_relaxed);
                return;
            }
            producer.wait_entry_reason.store(NormalizeReason(old_wait_reason),
                                             std::memory_order_release);
            return;
        }

        if (old_state == Waiting && new_state != Waiting) {
            const u64 start_ns = producer.wait_start_ns.exchange(0, std::memory_order_acq_rel);
            if (start_ns == 0 || now_ns < start_ns) {
                producer.malformed_waits.fetch_add(1, std::memory_order_relaxed);
                return;
            }

            const u64 duration_ns = now_ns - start_ns;
            const u32 entry_reason =
                producer.wait_entry_reason.exchange(0, std::memory_order_acq_rel);
            const u32 exit_reason = NormalizeReason(old_wait_reason);
            const u32 reason = exit_reason != 0 ? exit_reason : entry_reason;

            producer.current_interval_wait_ns.fetch_add(duration_ns, std::memory_order_relaxed);
            producer.reason_count[reason].fetch_add(1, std::memory_order_relaxed);
            producer.reason_ns[reason].fetch_add(duration_ns, std::memory_order_relaxed);
        }
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

        std::array<CandidateSnapshot, CandidateSlotCount> candidate_snapshot{};
        for (size_t i = 0; i < CandidateSlotCount; ++i) {
            candidate_snapshot[i].address = candidates[i].address.load(std::memory_order_relaxed);
            candidate_snapshot[i].thread_id = candidates[i].thread_id.load(std::memory_order_relaxed);
            candidate_snapshot[i].calls = candidates[i].calls.exchange(0, std::memory_order_relaxed);
        }

        u64 next_address = 0;
        std::array<u64, ProducerCount> next_tid{};
        std::array<u64, ProducerCount> next_calls{};
        SelectNextTracking(candidate_snapshot, next_address, next_tid, next_calls);

        const u64 current_address = tracked_address.load(std::memory_order_relaxed);
        const u64 current_tid0 = producers[0].thread_id.load(std::memory_order_relaxed);
        const u64 current_tid1 = producers[1].thread_id.load(std::memory_order_relaxed);
        const auto p0 = SnapshotAndResetWindow(producers[0]);
        const auto p1 = SnapshotAndResetWindow(producers[1]);

        LOG_INFO(
            HW_GPU,
            "[X1-WAKERF] frame={} frames={} trackedAddr={:#x} nextAddr={:#x} next0={:#x}/{}x next1={:#x}/{}x "
            "p0Tid={:#x} p0signals={} p0intervals={} p0interAvg={:.3f}ms p0interMax={:.3f}ms "
            "p0waitAvg={:.3f}ms p0residualAvg={:.3f}ms p0cpuAvg={:.3f}ms p0cpuMax={:.3f}ms "
            "p0runUnschedAvg={:.3f}ms p0runUnschedMax={:.3f}ms p0noneN={} p0none={:.3f}ms "
            "p0sleepN={} p0sleep={:.3f}ms p0ipcN={} p0ipc={:.3f}ms p0syncN={} p0sync={:.3f}ms "
            "p0condN={} p0cond={:.3f}ms p0arbN={} p0arb={:.3f}ms p0suspN={} p0susp={:.3f}ms "
            "p0prio={} p0activeCore={} p0currentCore={} p0cpuOver={} p0malCpu={} p0malWait={} p0malInt={} "
            "p1Tid={:#x} p1signals={} p1intervals={} p1interAvg={:.3f}ms p1interMax={:.3f}ms "
            "p1waitAvg={:.3f}ms p1residualAvg={:.3f}ms p1cpuAvg={:.3f}ms p1cpuMax={:.3f}ms "
            "p1runUnschedAvg={:.3f}ms p1runUnschedMax={:.3f}ms p1noneN={} p1none={:.3f}ms "
            "p1sleepN={} p1sleep={:.3f}ms p1ipcN={} p1ipc={:.3f}ms p1syncN={} p1sync={:.3f}ms "
            "p1condN={} p1cond={:.3f}ms p1arbN={} p1arb={:.3f}ms p1suspN={} p1susp={:.3f}ms "
            "p1prio={} p1activeCore={} p1currentCore={} p1cpuOver={} p1malCpu={} p1malWait={} p1malInt={} "
            "candidateOverflow={} trackingSwitch={}",
            frame, frames, current_address, next_address, next_tid[0], next_calls[0], next_tid[1],
            next_calls[1], current_tid0, p0.signal_calls, p0.interval_count,
            AvgMs(p0.inter_total_ns, p0.interval_count), ToMs(p0.inter_max_ns),
            AvgMs(p0.wait_total_ns, p0.interval_count),
            AvgMs(p0.residual_total_ns, p0.interval_count),
            AvgMs(p0.cpu_total_ns, p0.interval_count), ToMs(p0.cpu_max_ns),
            AvgMs(p0.run_unscheduled_total_ns, p0.interval_count), ToMs(p0.run_unscheduled_max_ns),
            p0.reason_count[0], ToMs(p0.reason_ns[0]), p0.reason_count[1], ToMs(p0.reason_ns[1]),
            p0.reason_count[2], ToMs(p0.reason_ns[2]), p0.reason_count[3], ToMs(p0.reason_ns[3]),
            p0.reason_count[4], ToMs(p0.reason_ns[4]), p0.reason_count[5], ToMs(p0.reason_ns[5]),
            p0.reason_count[6], ToMs(p0.reason_ns[6]), p0.priority, p0.active_core, p0.current_core,
            p0.cpu_over_residual, p0.malformed_cpu, p0.malformed_waits, p0.malformed_intervals,
            current_tid1, p1.signal_calls, p1.interval_count,
            AvgMs(p1.inter_total_ns, p1.interval_count), ToMs(p1.inter_max_ns),
            AvgMs(p1.wait_total_ns, p1.interval_count),
            AvgMs(p1.residual_total_ns, p1.interval_count),
            AvgMs(p1.cpu_total_ns, p1.interval_count), ToMs(p1.cpu_max_ns),
            AvgMs(p1.run_unscheduled_total_ns, p1.interval_count), ToMs(p1.run_unscheduled_max_ns),
            p1.reason_count[0], ToMs(p1.reason_ns[0]), p1.reason_count[1], ToMs(p1.reason_ns[1]),
            p1.reason_count[2], ToMs(p1.reason_ns[2]), p1.reason_count[3], ToMs(p1.reason_ns[3]),
            p1.reason_count[4], ToMs(p1.reason_ns[4]), p1.reason_count[5], ToMs(p1.reason_ns[5]),
            p1.reason_count[6], ToMs(p1.reason_ns[6]), p1.priority, p1.active_core, p1.current_core,
            p1.cpu_over_residual, p1.malformed_cpu, p1.malformed_waits, p1.malformed_intervals,
            candidate_overflow.exchange(0, std::memory_order_relaxed),
            tracking_switches.exchange(0, std::memory_order_relaxed));

        ApplyTracking(next_address, next_tid);
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ProducerCount = 2;
    static constexpr size_t CandidateSlotCount = 16;
    static constexpr size_t ReasonCount = 7;
    static constexpr u32 InvalidSlot = (std::numeric_limits<u32>::max)();

    struct CandidateSlot {
        std::atomic<u64> address{0};
        std::atomic<u64> thread_id{0};
        std::atomic<u64> calls{0};
    };

    struct CandidateSnapshot {
        u64 address{};
        u64 thread_id{};
        u64 calls{};
    };

    struct ProducerState {
        std::atomic<u64> thread_id{0};
        std::atomic<u64> signal_calls{0};
        std::atomic<u64> previous_signal_ns{0};
        std::atomic<u64> previous_cpu_ticks{0};
        std::atomic<u64> previous_clock_ticks{0};
        std::atomic<u64> interval_count{0};
        std::atomic<u64> inter_total_ns{0};
        std::atomic<u64> inter_max_ns{0};
        std::atomic<u64> wait_total_ns{0};
        std::atomic<u64> residual_total_ns{0};
        std::atomic<u64> cpu_total_ns{0};
        std::atomic<u64> cpu_max_ns{0};
        std::atomic<u64> runnable_unscheduled_total_ns{0};
        std::atomic<u64> runnable_unscheduled_max_ns{0};
        std::atomic<u64> current_interval_wait_ns{0};
        std::atomic<u64> wait_start_ns{0};
        std::atomic<u32> wait_entry_reason{0};
        std::array<std::atomic<u64>, ReasonCount> reason_count{};
        std::array<std::atomic<u64>, ReasonCount> reason_ns{};
        std::atomic<s32> latest_priority{0};
        std::atomic<s32> latest_active_core{-1};
        std::atomic<s32> latest_current_core{-1};
        std::atomic<u64> malformed_waits{0};
        std::atomic<u64> malformed_intervals{0};
        std::atomic<u64> malformed_cpu{0};
        std::atomic<u64> cpu_over_residual{0};
    };

    struct ProducerSnapshot {
        u64 signal_calls{};
        u64 interval_count{};
        u64 inter_total_ns{};
        u64 inter_max_ns{};
        u64 wait_total_ns{};
        u64 residual_total_ns{};
        u64 cpu_total_ns{};
        u64 cpu_max_ns{};
        u64 run_unscheduled_total_ns{};
        u64 run_unscheduled_max_ns{};
        std::array<u64, ReasonCount> reason_count{};
        std::array<u64, ReasonCount> reason_ns{};
        s32 priority{};
        s32 active_core{-1};
        s32 current_core{-1};
        u64 malformed_waits{};
        u64 malformed_intervals{};
        u64 malformed_cpu{};
        u64 cpu_over_residual{};
    };

    static u64 NowNs() noexcept {
        return static_cast<u64>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                    Clock::now().time_since_epoch())
                                    .count());
    }

    static u32 NormalizeReason(u32 reason) noexcept {
        return reason < ReasonCount ? reason : 0;
    }

    static u64 ScaleTicksToNs(u64 cpu_delta, u64 elapsed_ns, u64 clock_delta) noexcept {
        if (clock_delta == 0 || cpu_delta == 0 || elapsed_ns == 0) {
            return 0;
        }
        const long double scaled = static_cast<long double>(cpu_delta) *
                                   static_cast<long double>(elapsed_ns) /
                                   static_cast<long double>(clock_delta);
        return scaled > static_cast<long double>((std::numeric_limits<u64>::max)())
                   ? (std::numeric_limits<u64>::max)()
                   : static_cast<u64>(scaled);
    }

    static double ToMs(u64 ns) noexcept {
        return static_cast<double>(ns) / 1'000'000.0;
    }

    static double AvgMs(u64 ns, u64 count) noexcept {
        return count == 0 ? 0.0 : ToMs(ns) / static_cast<double>(count);
    }

    static void AtomicMax(std::atomic<u64>& target, u64 value) noexcept {
        u64 current = target.load(std::memory_order_relaxed);
        while (current < value &&
               !target.compare_exchange_weak(current, value, std::memory_order_relaxed,
                                             std::memory_order_relaxed)) {
        }
    }

    u32 FindOrClaimCandidate(u64 address, u64 thread_id) noexcept {
        for (u32 i = 0; i < CandidateSlotCount; ++i) {
            auto& slot = candidates[i];
            if (slot.address.load(std::memory_order_acquire) == address &&
                slot.thread_id.load(std::memory_order_acquire) == thread_id) {
                return i;
            }
        }
        for (u32 i = 0; i < CandidateSlotCount; ++i) {
            auto& slot = candidates[i];
            u64 expected = 0;
            if (slot.address.compare_exchange_strong(expected, address, std::memory_order_acq_rel,
                                                     std::memory_order_relaxed)) {
                slot.thread_id.store(thread_id, std::memory_order_release);
                return i;
            }
            if (expected == address &&
                slot.thread_id.load(std::memory_order_acquire) == thread_id) {
                return i;
            }
        }
        return InvalidSlot;
    }

    u32 FindTrackedProducer(u64 thread_id) const noexcept {
        for (u32 i = 0; i < ProducerCount; ++i) {
            if (producers[i].thread_id.load(std::memory_order_acquire) == thread_id &&
                thread_id != 0) {
                return i;
            }
        }
        return InvalidSlot;
    }

    static void SelectNextTracking(const std::array<CandidateSnapshot, CandidateSlotCount>& snapshot,
                                   u64& next_address, std::array<u64, ProducerCount>& next_tid,
                                   std::array<u64, ProducerCount>& next_calls) noexcept {
        u64 best_address_calls = 0;
        for (const auto& candidate : snapshot) {
            if (candidate.address == 0 || candidate.calls == 0) {
                continue;
            }
            u64 address_calls = 0;
            for (const auto& peer : snapshot) {
                if (peer.address == candidate.address) {
                    address_calls += peer.calls;
                }
            }
            if (address_calls > best_address_calls) {
                best_address_calls = address_calls;
                next_address = candidate.address;
            }
        }

        if (next_address == 0) {
            return;
        }

        for (const auto& candidate : snapshot) {
            if (candidate.address != next_address || candidate.thread_id == 0 || candidate.calls == 0) {
                continue;
            }
            for (size_t pos = 0; pos < ProducerCount; ++pos) {
                if (candidate.calls <= next_calls[pos]) {
                    continue;
                }
                for (size_t shift = ProducerCount - 1; shift > pos; --shift) {
                    next_calls[shift] = next_calls[shift - 1];
                    next_tid[shift] = next_tid[shift - 1];
                }
                next_calls[pos] = candidate.calls;
                next_tid[pos] = candidate.thread_id;
                break;
            }
        }
    }

    static ProducerSnapshot SnapshotAndResetWindow(ProducerState& producer) noexcept {
        ProducerSnapshot snap{};
        snap.signal_calls = producer.signal_calls.exchange(0, std::memory_order_relaxed);
        snap.interval_count = producer.interval_count.exchange(0, std::memory_order_relaxed);
        snap.inter_total_ns = producer.inter_total_ns.exchange(0, std::memory_order_relaxed);
        snap.inter_max_ns = producer.inter_max_ns.exchange(0, std::memory_order_relaxed);
        snap.wait_total_ns = producer.wait_total_ns.exchange(0, std::memory_order_relaxed);
        snap.residual_total_ns = producer.residual_total_ns.exchange(0, std::memory_order_relaxed);
        snap.cpu_total_ns = producer.cpu_total_ns.exchange(0, std::memory_order_relaxed);
        snap.cpu_max_ns = producer.cpu_max_ns.exchange(0, std::memory_order_relaxed);
        snap.run_unscheduled_total_ns =
            producer.runnable_unscheduled_total_ns.exchange(0, std::memory_order_relaxed);
        snap.run_unscheduled_max_ns =
            producer.runnable_unscheduled_max_ns.exchange(0, std::memory_order_relaxed);
        for (size_t i = 0; i < ReasonCount; ++i) {
            snap.reason_count[i] = producer.reason_count[i].exchange(0, std::memory_order_relaxed);
            snap.reason_ns[i] = producer.reason_ns[i].exchange(0, std::memory_order_relaxed);
        }
        snap.priority = producer.latest_priority.load(std::memory_order_relaxed);
        snap.active_core = producer.latest_active_core.load(std::memory_order_relaxed);
        snap.current_core = producer.latest_current_core.load(std::memory_order_relaxed);
        snap.malformed_waits = producer.malformed_waits.exchange(0, std::memory_order_relaxed);
        snap.malformed_intervals =
            producer.malformed_intervals.exchange(0, std::memory_order_relaxed);
        snap.malformed_cpu = producer.malformed_cpu.exchange(0, std::memory_order_relaxed);
        snap.cpu_over_residual =
            producer.cpu_over_residual.exchange(0, std::memory_order_relaxed);
        return snap;
    }

    static void ResetProducerAnchors(ProducerState& producer) noexcept {
        producer.previous_signal_ns.store(0, std::memory_order_relaxed);
        producer.previous_cpu_ticks.store(0, std::memory_order_relaxed);
        producer.previous_clock_ticks.store(0, std::memory_order_relaxed);
        producer.current_interval_wait_ns.store(0, std::memory_order_relaxed);
        producer.wait_start_ns.store(0, std::memory_order_relaxed);
        producer.wait_entry_reason.store(0, std::memory_order_relaxed);
    }

    static void ResetProducerAll(ProducerState& producer) noexcept {
        producer.thread_id.store(0, std::memory_order_relaxed);
        producer.signal_calls.store(0, std::memory_order_relaxed);
        ResetProducerAnchors(producer);
        producer.interval_count.store(0, std::memory_order_relaxed);
        producer.inter_total_ns.store(0, std::memory_order_relaxed);
        producer.inter_max_ns.store(0, std::memory_order_relaxed);
        producer.wait_total_ns.store(0, std::memory_order_relaxed);
        producer.residual_total_ns.store(0, std::memory_order_relaxed);
        producer.cpu_total_ns.store(0, std::memory_order_relaxed);
        producer.cpu_max_ns.store(0, std::memory_order_relaxed);
        producer.runnable_unscheduled_total_ns.store(0, std::memory_order_relaxed);
        producer.runnable_unscheduled_max_ns.store(0, std::memory_order_relaxed);
        for (auto& value : producer.reason_count) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : producer.reason_ns) {
            value.store(0, std::memory_order_relaxed);
        }
        producer.latest_priority.store(0, std::memory_order_relaxed);
        producer.latest_active_core.store(-1, std::memory_order_relaxed);
        producer.latest_current_core.store(-1, std::memory_order_relaxed);
        producer.malformed_waits.store(0, std::memory_order_relaxed);
        producer.malformed_intervals.store(0, std::memory_order_relaxed);
        producer.malformed_cpu.store(0, std::memory_order_relaxed);
        producer.cpu_over_residual.store(0, std::memory_order_relaxed);
    }

    void ApplyTracking(u64 next_address, const std::array<u64, ProducerCount>& next_tid) noexcept {
        const u64 old_address = tracked_address.load(std::memory_order_acquire);
        const bool address_changed = old_address != next_address;
        if (address_changed) {
            tracked_address.store(next_address, std::memory_order_release);
        }

        for (size_t i = 0; i < ProducerCount; ++i) {
            auto& producer = producers[i];
            const u64 old_tid = producer.thread_id.load(std::memory_order_acquire);
            if (!address_changed && old_tid == next_tid[i]) {
                continue;
            }
            producer.thread_id.store(0, std::memory_order_release);
            ResetProducerAnchors(producer);
            producer.thread_id.store(next_tid[i], std::memory_order_release);
            tracking_switches.fetch_add(1, std::memory_order_relaxed);
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> tracked_address{0};
    std::array<CandidateSlot, CandidateSlotCount> candidates{};
    std::array<ProducerState, ProducerCount> producers{};
    std::atomic<u64> candidate_overflow{0};
    std::atomic<u64> tracking_switches{0};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
};

} // namespace Core
