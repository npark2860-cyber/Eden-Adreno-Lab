// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1WakerPreSignalProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1WakerPreSignalProfiler& Get() {
        static X1WakerPreSignalProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_address_arbiter_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        waker_tid.store(0, std::memory_order_relaxed);
        signal_calls.store(0, std::memory_order_relaxed);
        waker_switches.store(0, std::memory_order_relaxed);
        inter_signal_start_ns.store(0, std::memory_order_relaxed);
        inter_signal_count.store(0, std::memory_order_relaxed);
        inter_signal_total_ns.store(0, std::memory_order_relaxed);
        inter_signal_max_ns.store(0, std::memory_order_relaxed);
        closed_interval_wait_ns.store(0, std::memory_order_relaxed);
        residual_total_ns.store(0, std::memory_order_relaxed);
        residual_max_ns.store(0, std::memory_order_relaxed);
        current_interval_wait_ns.store(0, std::memory_order_relaxed);
        wait_start_ns.store(0, std::memory_order_relaxed);
        wait_start_reason.store(0, std::memory_order_relaxed);
        wait_start_svc.store(0, std::memory_order_relaxed);
        last_wait_svc.store(0, std::memory_order_relaxed);
        wait_begins.store(0, std::memory_order_relaxed);
        wait_ends.store(0, std::memory_order_relaxed);
        orphan_wait_ends.store(0, std::memory_order_relaxed);
        nested_wait_begins.store(0, std::memory_order_relaxed);
        malformed_waits.store(0, std::memory_order_relaxed);
        malformed_intervals.store(0, std::memory_order_relaxed);
        report_pc_ref.store(0, std::memory_order_relaxed);
        report_pc_mismatch.store(0, std::memory_order_relaxed);
        report_lr_ref.store(0, std::memory_order_relaxed);
        report_lr_mismatch.store(0, std::memory_order_relaxed);
        latest_pc.store(0, std::memory_order_relaxed);
        latest_lr.store(0, std::memory_order_relaxed);
        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;
        report_start = Clock::now();

        for (auto& value : current_reason_count) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : current_reason_ns) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : report_reason_count) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : report_reason_ns) {
            value.store(0, std::memory_order_relaxed);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    [[nodiscard]] bool ShouldTrackThread(u64 thread_id) const noexcept {
        const u64 tracked = waker_tid.load(std::memory_order_acquire);
        return Enabled() && tracked != 0 && thread_id == tracked;
    }

    void RecordMatchingSignal(u64 thread_id, u64 guest_pc, u64 guest_lr) noexcept {
        if (!Enabled() || thread_id == 0) {
            return;
        }

        u64 tracked = waker_tid.load(std::memory_order_acquire);
        if (tracked == 0) {
            u64 expected = 0;
            if (waker_tid.compare_exchange_strong(expected, thread_id, std::memory_order_acq_rel,
                                                  std::memory_order_relaxed)) {
                tracked = thread_id;
            } else {
                tracked = expected;
            }
        }
        if (tracked != thread_id) {
            waker_switches.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        signal_calls.fetch_add(1, std::memory_order_relaxed);
        RecordCallsite(guest_pc, guest_lr);

        const u64 now_ns = NowNs();
        const u64 previous_ns = inter_signal_start_ns.exchange(now_ns, std::memory_order_acq_rel);
        if (previous_ns == 0) {
            ResetCurrentInterval();
            return;
        }
        if (now_ns < previous_ns) {
            malformed_intervals.fetch_add(1, std::memory_order_relaxed);
            ResetCurrentInterval();
            return;
        }

        const u64 elapsed_ns = now_ns - previous_ns;
        const u64 interval_wait_ns =
            current_interval_wait_ns.exchange(0, std::memory_order_acq_rel);

        inter_signal_count.fetch_add(1, std::memory_order_relaxed);
        inter_signal_total_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
        AtomicMax(inter_signal_max_ns, elapsed_ns);

        if (interval_wait_ns <= elapsed_ns) {
            closed_interval_wait_ns.fetch_add(interval_wait_ns, std::memory_order_relaxed);
            const u64 residual_ns = elapsed_ns - interval_wait_ns;
            residual_total_ns.fetch_add(residual_ns, std::memory_order_relaxed);
            AtomicMax(residual_max_ns, residual_ns);
        } else {
            malformed_intervals.fetch_add(1, std::memory_order_relaxed);
        }

        for (size_t i = 0; i < ReasonCount; ++i) {
            const u64 count = current_reason_count[i].exchange(0, std::memory_order_acq_rel);
            const u64 ns = current_reason_ns[i].exchange(0, std::memory_order_acq_rel);
            report_reason_count[i].fetch_add(count, std::memory_order_relaxed);
            report_reason_ns[i].fetch_add(ns, std::memory_order_relaxed);
        }
    }

    void RecordThreadStateTransition(u64 thread_id, u32 old_state, u32 new_state,
                                     u32 old_wait_reason, u8 current_svc_id) noexcept {
        if (!ShouldTrackThread(thread_id)) {
            return;
        }

        constexpr u32 Waiting = 1;
        const u64 now_ns = NowNs();

        if (old_state != Waiting && new_state == Waiting) {
            u64 expected = 0;
            if (wait_start_ns.compare_exchange_strong(expected, now_ns, std::memory_order_acq_rel,
                                                      std::memory_order_relaxed)) {
                wait_start_reason.store(old_wait_reason < ReasonCount ? old_wait_reason : 0,
                                        std::memory_order_release);
                wait_start_svc.store(current_svc_id, std::memory_order_release);
                wait_begins.fetch_add(1, std::memory_order_relaxed);
            } else {
                nested_wait_begins.fetch_add(1, std::memory_order_relaxed);
            }
            return;
        }

        if (old_state == Waiting && new_state != Waiting) {
            const u64 start_ns = wait_start_ns.exchange(0, std::memory_order_acq_rel);
            if (start_ns == 0) {
                orphan_wait_ends.fetch_add(1, std::memory_order_relaxed);
                return;
            }
            if (now_ns < start_ns) {
                malformed_waits.fetch_add(1, std::memory_order_relaxed);
                return;
            }

            const u64 duration_ns = now_ns - start_ns;
            const u32 reason = wait_start_reason.exchange(0, std::memory_order_acq_rel);
            const u8 svc = wait_start_svc.exchange(0, std::memory_order_acq_rel);

            current_interval_wait_ns.fetch_add(duration_ns, std::memory_order_relaxed);
            current_reason_count[reason].fetch_add(1, std::memory_order_relaxed);
            current_reason_ns[reason].fetch_add(duration_ns, std::memory_order_relaxed);
            last_wait_svc.store(svc, std::memory_order_relaxed);
            wait_ends.fetch_add(1, std::memory_order_relaxed);
        }
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

        const u64 signals = signal_calls.exchange(0, std::memory_order_relaxed);
        const u64 intervals = inter_signal_count.exchange(0, std::memory_order_relaxed);
        const u64 inter_ns = inter_signal_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 inter_max_ns = inter_signal_max_ns.exchange(0, std::memory_order_relaxed);
        const u64 wait_ns = closed_interval_wait_ns.exchange(0, std::memory_order_relaxed);
        const u64 residual_ns = residual_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 residual_max = residual_max_ns.exchange(0, std::memory_order_relaxed);

        std::array<u64, ReasonCount> reason_counts{};
        std::array<u64, ReasonCount> reason_times{};
        for (size_t i = 0; i < ReasonCount; ++i) {
            reason_counts[i] = report_reason_count[i].exchange(0, std::memory_order_relaxed);
            reason_times[i] = report_reason_ns[i].exchange(0, std::memory_order_relaxed);
        }

        const double wait_share = inter_ns == 0
                                      ? 0.0
                                      : 100.0 * static_cast<double>(wait_ns) /
                                            static_cast<double>(inter_ns);

        const u64 pc_ref = report_pc_ref.exchange(0, std::memory_order_relaxed);
        const u64 lr_ref = report_lr_ref.exchange(0, std::memory_order_relaxed);

        LOG_INFO(HW_GPU,
                 "[X1-WAKER] frame={} frames={} wall={:.3f}ms wakerTid={:#x} signals={} "
                 "intervals={} inter={:.3f}ms interAvg={:.3f}ms interMax={:.3f}ms "
                 "wait={:.3f}ms waitShare={:.2f}% residual={:.3f}ms residualAvg={:.3f}ms "
                 "residualMax={:.3f}ms noneN={} none={:.3f}ms sleepN={} sleep={:.3f}ms "
                 "ipcN={} ipc={:.3f}ms syncN={} sync={:.3f}ms condN={} cond={:.3f}ms "
                 "arbN={} arb={:.3f}ms suspN={} susp={:.3f}ms lastWaitSvc={:#x} "
                 "pc={:#x}/var{} lr={:#x}/var{} latestPc={:#x} latestLr={:#x} "
                 "begins={} ends={} orphanEnd={} nestedBegin={} malformedWait={} "
                 "malformedInterval={} wakerSwitch={}",
                 frame, frames, ToMs(wall_ns), waker_tid.load(std::memory_order_relaxed), signals,
                 intervals, ToMs(inter_ns), AvgMs(inter_ns, intervals), ToMs(inter_max_ns),
                 ToMs(wait_ns), wait_share, ToMs(residual_ns), AvgMs(residual_ns, intervals),
                 ToMs(residual_max), reason_counts[0], ToMs(reason_times[0]), reason_counts[1],
                 ToMs(reason_times[1]), reason_counts[2], ToMs(reason_times[2]), reason_counts[3],
                 ToMs(reason_times[3]), reason_counts[4], ToMs(reason_times[4]), reason_counts[5],
                 ToMs(reason_times[5]), reason_counts[6], ToMs(reason_times[6]),
                 last_wait_svc.load(std::memory_order_relaxed), pc_ref,
                 report_pc_mismatch.exchange(0, std::memory_order_relaxed), lr_ref,
                 report_lr_mismatch.exchange(0, std::memory_order_relaxed),
                 latest_pc.load(std::memory_order_relaxed), latest_lr.load(std::memory_order_relaxed),
                 wait_begins.exchange(0, std::memory_order_relaxed),
                 wait_ends.exchange(0, std::memory_order_relaxed),
                 orphan_wait_ends.exchange(0, std::memory_order_relaxed),
                 nested_wait_begins.exchange(0, std::memory_order_relaxed),
                 malformed_waits.exchange(0, std::memory_order_relaxed),
                 malformed_intervals.exchange(0, std::memory_order_relaxed),
                 waker_switches.exchange(0, std::memory_order_relaxed));
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ReasonCount = 7;

    static u64 NowNs() noexcept {
        return static_cast<u64>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                    Clock::now().time_since_epoch())
                                    .count());
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

    void ResetCurrentInterval() noexcept {
        current_interval_wait_ns.store(0, std::memory_order_relaxed);
        for (auto& value : current_reason_count) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : current_reason_ns) {
            value.store(0, std::memory_order_relaxed);
        }
    }

    void RecordCallsite(u64 guest_pc, u64 guest_lr) noexcept {
        latest_pc.store(guest_pc, std::memory_order_relaxed);
        latest_lr.store(guest_lr, std::memory_order_relaxed);

        u64 pc = report_pc_ref.load(std::memory_order_acquire);
        if (pc == 0) {
            u64 expected = 0;
            report_pc_ref.compare_exchange_strong(expected, guest_pc, std::memory_order_acq_rel,
                                                  std::memory_order_relaxed);
            pc = report_pc_ref.load(std::memory_order_acquire);
        }
        if (pc != guest_pc) {
            report_pc_mismatch.fetch_add(1, std::memory_order_relaxed);
        }

        u64 lr = report_lr_ref.load(std::memory_order_acquire);
        if (lr == 0) {
            u64 expected = 0;
            report_lr_ref.compare_exchange_strong(expected, guest_lr, std::memory_order_acq_rel,
                                                  std::memory_order_relaxed);
            lr = report_lr_ref.load(std::memory_order_acquire);
        }
        if (lr != guest_lr) {
            report_lr_mismatch.fetch_add(1, std::memory_order_relaxed);
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> waker_tid{0};
    std::atomic<u64> signal_calls{0};
    std::atomic<u64> waker_switches{0};

    std::atomic<u64> inter_signal_start_ns{0};
    std::atomic<u64> inter_signal_count{0};
    std::atomic<u64> inter_signal_total_ns{0};
    std::atomic<u64> inter_signal_max_ns{0};
    std::atomic<u64> closed_interval_wait_ns{0};
    std::atomic<u64> residual_total_ns{0};
    std::atomic<u64> residual_max_ns{0};

    std::atomic<u64> current_interval_wait_ns{0};
    std::array<std::atomic<u64>, ReasonCount> current_reason_count{};
    std::array<std::atomic<u64>, ReasonCount> current_reason_ns{};
    std::array<std::atomic<u64>, ReasonCount> report_reason_count{};
    std::array<std::atomic<u64>, ReasonCount> report_reason_ns{};

    std::atomic<u64> wait_start_ns{0};
    std::atomic<u32> wait_start_reason{0};
    std::atomic<u8> wait_start_svc{0};
    std::atomic<u8> last_wait_svc{0};
    std::atomic<u64> wait_begins{0};
    std::atomic<u64> wait_ends{0};
    std::atomic<u64> orphan_wait_ends{0};
    std::atomic<u64> nested_wait_begins{0};
    std::atomic<u64> malformed_waits{0};
    std::atomic<u64> malformed_intervals{0};

    std::atomic<u64> report_pc_ref{0};
    std::atomic<u64> report_pc_mismatch{0};
    std::atomic<u64> report_lr_ref{0};
    std::atomic<u64> report_lr_mismatch{0};
    std::atomic<u64> latest_pc{0};
    std::atomic<u64> latest_lr{0};

    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace Core
