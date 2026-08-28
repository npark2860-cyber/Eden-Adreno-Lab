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

class X1WakerStageDProfiler final {
public:
    enum class NoneWaitSite : u32 {
        Unknown = 0,
        ThreadSetActivityPinned = 1,
        ThreadSetCoreMaskPinned = 2,
        ProcessUserException = 3,
        Count = 4,
    };

    using Clock = std::chrono::steady_clock;

    static X1WakerStageDProfiler& Get() {
        static X1WakerStageDProfiler profiler;
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
        previous_signal_ns.store(0, std::memory_order_relaxed);
        previous_cpu_ticks.store(0, std::memory_order_relaxed);
        previous_clock_ticks.store(0, std::memory_order_relaxed);
        interval_count.store(0, std::memory_order_relaxed);
        inter_total_ns.store(0, std::memory_order_relaxed);
        inter_max_ns.store(0, std::memory_order_relaxed);
        wait_total_ns.store(0, std::memory_order_relaxed);
        residual_total_ns.store(0, std::memory_order_relaxed);
        cpu_total_ns.store(0, std::memory_order_relaxed);
        cpu_max_ns.store(0, std::memory_order_relaxed);
        runnable_unscheduled_total_ns.store(0, std::memory_order_relaxed);
        runnable_unscheduled_max_ns.store(0, std::memory_order_relaxed);
        current_interval_wait_ns.store(0, std::memory_order_relaxed);
        wait_start_ns.store(0, std::memory_order_relaxed);
        wait_entry_reason.store(0, std::memory_order_relaxed);
        wait_start_site.store(0, std::memory_order_relaxed);
        armed_none_wait_site.store(0, std::memory_order_relaxed);
        malformed_waits.store(0, std::memory_order_relaxed);
        malformed_intervals.store(0, std::memory_order_relaxed);
        malformed_cpu.store(0, std::memory_order_relaxed);
        cpu_over_residual.store(0, std::memory_order_relaxed);
        latest_pc.store(0, std::memory_order_relaxed);
        latest_priority.store(0, std::memory_order_relaxed);
        latest_active_core.store(-1, std::memory_order_relaxed);
        latest_current_core.store(-1, std::memory_order_relaxed);
        lr_overflow.store(0, std::memory_order_relaxed);
        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;

        for (auto& value : reason_count) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : reason_ns) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : none_site_count) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& value : none_site_ns) {
            value.store(0, std::memory_order_relaxed);
        }
        for (auto& slot : lr_slots) {
            slot.value.store(0, std::memory_order_relaxed);
            slot.count.store(0, std::memory_order_relaxed);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    [[nodiscard]] bool ShouldTrackThread(u64 thread_id) const noexcept {
        const u64 tracked = waker_tid.load(std::memory_order_acquire);
        return Enabled() && tracked != 0 && tracked == thread_id;
    }

    void ArmNoneWaitSite(u64 thread_id, NoneWaitSite site) noexcept {
        if (!ShouldTrackThread(thread_id)) {
            return;
        }
        const u32 raw = static_cast<u32>(site);
        if (raw < SiteCount) {
            armed_none_wait_site.store(raw, std::memory_order_release);
        }
    }

    void RecordMatchingSignal(u64 thread_id, u64 guest_pc, u64 guest_lr, u64 cpu_ticks,
                              u64 clock_ticks, s32 priority, s32 active_core,
                              s32 current_core) noexcept {
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
        latest_pc.store(guest_pc, std::memory_order_relaxed);
        latest_priority.store(priority, std::memory_order_relaxed);
        latest_active_core.store(active_core, std::memory_order_relaxed);
        latest_current_core.store(current_core, std::memory_order_relaxed);
        RecordLr(guest_lr);

        const u64 now_ns = NowNs();
        const u64 previous_ns = previous_signal_ns.exchange(now_ns, std::memory_order_acq_rel);
        const u64 previous_cpu = previous_cpu_ticks.exchange(cpu_ticks, std::memory_order_acq_rel);
        const u64 previous_clock =
            previous_clock_ticks.exchange(clock_ticks, std::memory_order_acq_rel);

        if (previous_ns == 0) {
            current_interval_wait_ns.store(0, std::memory_order_relaxed);
            return;
        }
        if (now_ns < previous_ns) {
            malformed_intervals.fetch_add(1, std::memory_order_relaxed);
            current_interval_wait_ns.store(0, std::memory_order_relaxed);
            return;
        }

        const u64 elapsed_ns = now_ns - previous_ns;
        const u64 interval_wait_ns =
            current_interval_wait_ns.exchange(0, std::memory_order_acq_rel);
        if (interval_wait_ns > elapsed_ns) {
            malformed_intervals.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        interval_count.fetch_add(1, std::memory_order_relaxed);
        inter_total_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
        AtomicMax(inter_max_ns, elapsed_ns);
        wait_total_ns.fetch_add(interval_wait_ns, std::memory_order_relaxed);

        const u64 residual_ns = elapsed_ns - interval_wait_ns;
        residual_total_ns.fetch_add(residual_ns, std::memory_order_relaxed);

        u64 cpu_ns = 0;
        if (cpu_ticks >= previous_cpu && clock_ticks > previous_clock) {
            const u64 cpu_delta = cpu_ticks - previous_cpu;
            const u64 clock_delta = clock_ticks - previous_clock;
            cpu_ns = ScaleTicksToNs(cpu_delta, elapsed_ns, clock_delta);
            cpu_total_ns.fetch_add(cpu_ns, std::memory_order_relaxed);
            AtomicMax(cpu_max_ns, cpu_ns);
        } else {
            malformed_cpu.fetch_add(1, std::memory_order_relaxed);
        }

        const u64 runnable_unscheduled_ns = residual_ns > cpu_ns ? residual_ns - cpu_ns : 0;
        if (cpu_ns > residual_ns) {
            cpu_over_residual.fetch_add(1, std::memory_order_relaxed);
        }
        runnable_unscheduled_total_ns.fetch_add(runnable_unscheduled_ns,
                                                 std::memory_order_relaxed);
        AtomicMax(runnable_unscheduled_max_ns, runnable_unscheduled_ns);
    }

    void RecordThreadStateTransition(u64 thread_id, u32 old_state, u32 new_state,
                                     u32 old_wait_reason) noexcept {
        if (!ShouldTrackThread(thread_id)) {
            return;
        }

        constexpr u32 Waiting = 1;
        const u64 now_ns = NowNs();

        if (old_state != Waiting && new_state == Waiting) {
            u64 expected = 0;
            if (!wait_start_ns.compare_exchange_strong(expected, now_ns, std::memory_order_acq_rel,
                                                       std::memory_order_relaxed)) {
                malformed_waits.fetch_add(1, std::memory_order_relaxed);
                return;
            }
            wait_entry_reason.store(NormalizeReason(old_wait_reason), std::memory_order_release);
            wait_start_site.store(armed_none_wait_site.exchange(0, std::memory_order_acq_rel),
                                  std::memory_order_release);
            return;
        }

        if (old_state == Waiting && new_state != Waiting) {
            const u64 start_ns = wait_start_ns.exchange(0, std::memory_order_acq_rel);
            if (start_ns == 0 || now_ns < start_ns) {
                malformed_waits.fetch_add(1, std::memory_order_relaxed);
                return;
            }

            const u64 duration_ns = now_ns - start_ns;
            const u32 entry_reason = wait_entry_reason.exchange(0, std::memory_order_acq_rel);
            const u32 exit_reason = NormalizeReason(old_wait_reason);
            const u32 reason = exit_reason != 0 ? exit_reason : entry_reason;
            const u32 site = wait_start_site.exchange(0, std::memory_order_acq_rel);

            current_interval_wait_ns.fetch_add(duration_ns, std::memory_order_relaxed);
            reason_count[reason].fetch_add(1, std::memory_order_relaxed);
            reason_ns[reason].fetch_add(duration_ns, std::memory_order_relaxed);

            if (reason == 0) {
                const u32 safe_site = site < SiteCount ? site : 0;
                none_site_count[safe_site].fetch_add(1, std::memory_order_relaxed);
                none_site_ns[safe_site].fetch_add(duration_ns, std::memory_order_relaxed);
            }
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

        const u64 signals = signal_calls.exchange(0, std::memory_order_relaxed);
        const u64 intervals = interval_count.exchange(0, std::memory_order_relaxed);
        const u64 inter_ns = inter_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 inter_max = inter_max_ns.exchange(0, std::memory_order_relaxed);
        const u64 wait_ns = wait_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 residual_ns = residual_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 cpu_ns = cpu_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 cpu_max = cpu_max_ns.exchange(0, std::memory_order_relaxed);
        const u64 run_unsched_ns =
            runnable_unscheduled_total_ns.exchange(0, std::memory_order_relaxed);
        const u64 run_unsched_max =
            runnable_unscheduled_max_ns.exchange(0, std::memory_order_relaxed);

        std::array<u64, ReasonCount> reason_counts{};
        std::array<u64, ReasonCount> reason_times{};
        for (size_t i = 0; i < ReasonCount; ++i) {
            reason_counts[i] = reason_count[i].exchange(0, std::memory_order_relaxed);
            reason_times[i] = reason_ns[i].exchange(0, std::memory_order_relaxed);
        }

        std::array<u64, SiteCount> site_counts{};
        std::array<u64, SiteCount> site_times{};
        for (size_t i = 0; i < SiteCount; ++i) {
            site_counts[i] = none_site_count[i].exchange(0, std::memory_order_relaxed);
            site_times[i] = none_site_ns[i].exchange(0, std::memory_order_relaxed);
        }

        std::array<u64, TopLrCount> top_lr_values{};
        std::array<u64, TopLrCount> top_lr_counts{};
        CollectTopLrs(top_lr_values, top_lr_counts);

        LOG_INFO(HW_GPU,
                 "[X1-WAKERD] frame={} frames={} wakerTid={:#x} signals={} intervals={} "
                 "interAvg={:.3f}ms interMax={:.3f}ms waitAvg={:.3f}ms residualAvg={:.3f}ms "
                 "cpuAvg={:.3f}ms cpuMax={:.3f}ms runUnschedAvg={:.3f}ms runUnschedMax={:.3f}ms "
                 "noneN={} none={:.3f}ms sleepN={} sleep={:.3f}ms ipcN={} ipc={:.3f}ms "
                 "syncN={} sync={:.3f}ms condN={} cond={:.3f}ms arbN={} arb={:.3f}ms "
                 "suspN={} susp={:.3f}ms noneUnknownN={} noneUnknown={:.3f}ms "
                 "noneActivityN={} noneActivity={:.3f}ms noneCoreMaskN={} noneCoreMask={:.3f}ms "
                 "noneUserExcN={} noneUserExc={:.3f}ms prio={} activeCore={} currentCore={} pc={:#x} "
                 "lr0={:#x}/{} lr1={:#x}/{} lr2={:#x}/{} lr3={:#x}/{} lrOverflow={} "
                 "cpuOverResidual={} malformedCpu={} malformedWait={} malformedInterval={} wakerSwitch={}",
                 frame, frames, waker_tid.load(std::memory_order_relaxed), signals, intervals,
                 AvgMs(inter_ns, intervals), ToMs(inter_max), AvgMs(wait_ns, intervals),
                 AvgMs(residual_ns, intervals), AvgMs(cpu_ns, intervals), ToMs(cpu_max),
                 AvgMs(run_unsched_ns, intervals), ToMs(run_unsched_max), reason_counts[0],
                 ToMs(reason_times[0]), reason_counts[1], ToMs(reason_times[1]), reason_counts[2],
                 ToMs(reason_times[2]), reason_counts[3], ToMs(reason_times[3]), reason_counts[4],
                 ToMs(reason_times[4]), reason_counts[5], ToMs(reason_times[5]), reason_counts[6],
                 ToMs(reason_times[6]), site_counts[0], ToMs(site_times[0]), site_counts[1],
                 ToMs(site_times[1]), site_counts[2], ToMs(site_times[2]), site_counts[3],
                 ToMs(site_times[3]), latest_priority.load(std::memory_order_relaxed),
                 latest_active_core.load(std::memory_order_relaxed),
                 latest_current_core.load(std::memory_order_relaxed),
                 latest_pc.load(std::memory_order_relaxed), top_lr_values[0], top_lr_counts[0],
                 top_lr_values[1], top_lr_counts[1], top_lr_values[2], top_lr_counts[2],
                 top_lr_values[3], top_lr_counts[3], lr_overflow.exchange(0, std::memory_order_relaxed),
                 cpu_over_residual.exchange(0, std::memory_order_relaxed),
                 malformed_cpu.exchange(0, std::memory_order_relaxed),
                 malformed_waits.exchange(0, std::memory_order_relaxed),
                 malformed_intervals.exchange(0, std::memory_order_relaxed),
                 waker_switches.exchange(0, std::memory_order_relaxed));
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ReasonCount = 7;
    static constexpr size_t SiteCount = static_cast<size_t>(NoneWaitSite::Count);
    static constexpr size_t LrSlotCount = 16;
    static constexpr size_t TopLrCount = 4;

    struct LrSlot {
        std::atomic<u64> value{0};
        std::atomic<u64> count{0};
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

    void RecordLr(u64 guest_lr) noexcept {
        if (guest_lr == 0) {
            lr_overflow.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        for (auto& slot : lr_slots) {
            if (slot.value.load(std::memory_order_acquire) == guest_lr) {
                slot.count.fetch_add(1, std::memory_order_relaxed);
                return;
            }
        }
        for (auto& slot : lr_slots) {
            u64 expected = 0;
            if (slot.value.compare_exchange_strong(expected, guest_lr, std::memory_order_acq_rel,
                                                   std::memory_order_relaxed)) {
                slot.count.fetch_add(1, std::memory_order_relaxed);
                return;
            }
            if (expected == guest_lr) {
                slot.count.fetch_add(1, std::memory_order_relaxed);
                return;
            }
        }
        lr_overflow.fetch_add(1, std::memory_order_relaxed);
    }

    void CollectTopLrs(std::array<u64, TopLrCount>& values,
                       std::array<u64, TopLrCount>& counts) noexcept {
        for (auto& slot : lr_slots) {
            const u64 count = slot.count.exchange(0, std::memory_order_relaxed);
            if (count == 0) {
                continue;
            }
            const u64 value = slot.value.load(std::memory_order_relaxed);
            for (size_t pos = 0; pos < TopLrCount; ++pos) {
                if (count <= counts[pos]) {
                    continue;
                }
                for (size_t shift = TopLrCount - 1; shift > pos; --shift) {
                    counts[shift] = counts[shift - 1];
                    values[shift] = values[shift - 1];
                }
                counts[pos] = count;
                values[pos] = value;
                break;
            }
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> waker_tid{0};
    std::atomic<u64> signal_calls{0};
    std::atomic<u64> waker_switches{0};

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
    std::atomic<u32> wait_start_site{0};
    std::atomic<u32> armed_none_wait_site{0};
    std::array<std::atomic<u64>, ReasonCount> reason_count{};
    std::array<std::atomic<u64>, ReasonCount> reason_ns{};
    std::array<std::atomic<u64>, SiteCount> none_site_count{};
    std::array<std::atomic<u64>, SiteCount> none_site_ns{};

    std::atomic<u64> malformed_waits{0};
    std::atomic<u64> malformed_intervals{0};
    std::atomic<u64> malformed_cpu{0};
    std::atomic<u64> cpu_over_residual{0};

    std::atomic<u64> latest_pc{0};
    std::atomic<s32> latest_priority{0};
    std::atomic<s32> latest_active_core{-1};
    std::atomic<s32> latest_current_core{-1};
    std::array<LrSlot, LrSlotCount> lr_slots{};
    std::atomic<u64> lr_overflow{0};

    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
};

} // namespace Core
