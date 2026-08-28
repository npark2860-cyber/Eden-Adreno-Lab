// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1GuestPostWaitProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1GuestPostWaitProfiler& Get() {
        static X1GuestPostWaitProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_guest_post_wait_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        target_tid.store(0, std::memory_order_relaxed);
        window_open.store(false, std::memory_order_relaxed);
        window_start_ns.store(0, std::memory_order_relaxed);
        wait_start_ns.store(0, std::memory_order_relaxed);
        wait_start_svc.store(0, std::memory_order_relaxed);
        ignore_reply_wake.store(false, std::memory_order_relaxed);
        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;
        report_start = Clock::now();
        ResetCounters();
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void RecordCandidateHandlerEntry(u64 thread_id) noexcept {
        if (!Enabled() || thread_id == 0) {
            return;
        }

        const u64 now_ns = NowNs();
        const u64 tracked = target_tid.load(std::memory_order_acquire);
        if (tracked != 0 && tracked != thread_id) {
            target_switches.fetch_add(1, std::memory_order_relaxed);
        }
        target_tid.store(thread_id, std::memory_order_release);

        if (window_open.exchange(false, std::memory_order_acq_rel)) {
            const u64 start_ns = window_start_ns.exchange(0, std::memory_order_acq_rel);
            if (start_ns != 0 && now_ns >= start_ns) {
                const u64 duration_ns = now_ns - start_ns;
                windows.fetch_add(1, std::memory_order_relaxed);
                window_ns.fetch_add(duration_ns, std::memory_order_relaxed);
                AtomicMax(window_max_ns, duration_ns);
            } else {
                malformed_windows.fetch_add(1, std::memory_order_relaxed);
            }
        }

        // The current candidate IPC wait began near A and ends only after this handler completes.
        // It is not part of the prior C -> next-candidate interval that we want to attribute.
        wait_start_ns.store(0, std::memory_order_release);
    }

    void RecordCandidateHandlerComplete(u64 thread_id) noexcept {
        if (!Enabled() || thread_id == 0) {
            return;
        }

        target_tid.store(thread_id, std::memory_order_release);
        wait_start_ns.store(0, std::memory_order_release);
        wait_start_svc.store(0, std::memory_order_relaxed);
        ignore_reply_wake.store(true, std::memory_order_release);
        window_start_ns.store(NowNs(), std::memory_order_release);
        window_open.store(true, std::memory_order_release);
    }

    void RecordThreadStateTransition(u64 thread_id, u32 old_state, u32 new_state,
                                     u32 old_wait_reason, u8 current_svc_id) noexcept {
        if (!Enabled() || thread_id == 0 ||
            thread_id != target_tid.load(std::memory_order_acquire) ||
            !window_open.load(std::memory_order_acquire)) {
            return;
        }

        constexpr u32 Waiting = 1;
        const u64 now_ns = NowNs();

        if (old_state != Waiting && new_state == Waiting) {
            u64 expected = 0;
            if (wait_start_ns.compare_exchange_strong(expected, now_ns, std::memory_order_acq_rel,
                                                      std::memory_order_relaxed)) {
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
                if (ignore_reply_wake.exchange(false, std::memory_order_acq_rel)) {
                    ignored_candidate_reply_wakes.fetch_add(1, std::memory_order_relaxed);
                } else {
                    orphan_wait_ends.fetch_add(1, std::memory_order_relaxed);
                }
                return;
            }

            ignore_reply_wake.store(false, std::memory_order_release);
            if (now_ns < start_ns) {
                malformed_waits.fetch_add(1, std::memory_order_relaxed);
                return;
            }

            const u64 duration_ns = now_ns - start_ns;
            const u32 reason = old_wait_reason < ReasonCount ? old_wait_reason : 0;
            const u32 svc = wait_start_svc.exchange(0, std::memory_order_acq_rel);

            wait_ends.fetch_add(1, std::memory_order_relaxed);
            reason_count[reason].fetch_add(1, std::memory_order_relaxed);
            reason_ns[reason].fetch_add(duration_ns, std::memory_order_relaxed);
            AtomicMax(reason_max_ns[reason], duration_ns);

            svc_count[svc].fetch_add(1, std::memory_order_relaxed);
            svc_ns[svc].fetch_add(duration_ns, std::memory_order_relaxed);
            AtomicMax(svc_max_ns[svc], duration_ns);
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

        const u64 window_count = windows.exchange(0, std::memory_order_relaxed);
        const u64 total_window_ns = window_ns.exchange(0, std::memory_order_relaxed);
        const u64 max_window_ns = window_max_ns.exchange(0, std::memory_order_relaxed);

        std::array<u64, ReasonCount> counts{};
        std::array<u64, ReasonCount> times{};
        u64 total_wait_ns{};
        for (size_t i = 0; i < ReasonCount; ++i) {
            counts[i] = reason_count[i].exchange(0, std::memory_order_relaxed);
            times[i] = reason_ns[i].exchange(0, std::memory_order_relaxed);
            reason_max_ns[i].exchange(0, std::memory_order_relaxed);
            total_wait_ns += times[i];
        }

        struct TopSvc {
            u32 id{};
            u64 count{};
            u64 ns{};
        };
        std::array<TopSvc, 3> top{};
        for (u32 i = 0; i < SvcCount; ++i) {
            const u64 count = svc_count[i].exchange(0, std::memory_order_relaxed);
            const u64 ns = svc_ns[i].exchange(0, std::memory_order_relaxed);
            svc_max_ns[i].exchange(0, std::memory_order_relaxed);
            if (ns == 0) {
                continue;
            }
            TopSvc candidate{i, count, ns};
            for (auto& slot : top) {
                if (candidate.ns > slot.ns) {
                    std::swap(candidate, slot);
                }
            }
        }

        const u64 residual_ns = total_window_ns > total_wait_ns ? total_window_ns - total_wait_ns : 0;
        const double wait_share = total_window_ns == 0
                                      ? 0.0
                                      : 100.0 * static_cast<double>(total_wait_ns) /
                                            static_cast<double>(total_window_ns);

        LOG_INFO(HW_GPU,
                 "[X1-GUESTWAIT] frame={} frames={} wall={:.3f}ms tid={:#x} windows={} "
                 "window={:.3f}ms windowAvg={:.3f}ms windowMax={:.3f}ms wait={:.3f}ms "
                 "waitShare={:.2f}% residual={:.3f}ms noneN={} none={:.3f}ms "
                 "sleepN={} sleep={:.3f}ms ipcN={} ipc={:.3f}ms syncN={} sync={:.3f}ms "
                 "condN={} cond={:.3f}ms arbN={} arb={:.3f}ms suspN={} susp={:.3f}ms "
                 "topSvc0={:#x}/{}x/{:.3f}ms topSvc1={:#x}/{}x/{:.3f}ms "
                 "topSvc2={:#x}/{}x/{:.3f}ms begins={} ends={} ignoredReplyWake={} "
                 "orphanEnd={} nestedBegin={} malformedWait={} malformedWindow={} targetSwitch={}",
                 frame, frames, ToMs(wall_ns), target_tid.load(std::memory_order_relaxed),
                 window_count, ToMs(total_window_ns), AvgMs(total_window_ns, window_count),
                 ToMs(max_window_ns), ToMs(total_wait_ns), wait_share, ToMs(residual_ns),
                 counts[0], ToMs(times[0]), counts[1], ToMs(times[1]), counts[2], ToMs(times[2]),
                 counts[3], ToMs(times[3]), counts[4], ToMs(times[4]), counts[5], ToMs(times[5]),
                 counts[6], ToMs(times[6]), top[0].id, top[0].count, ToMs(top[0].ns), top[1].id,
                 top[1].count, ToMs(top[1].ns), top[2].id, top[2].count, ToMs(top[2].ns),
                 wait_begins.exchange(0, std::memory_order_relaxed),
                 wait_ends.exchange(0, std::memory_order_relaxed),
                 ignored_candidate_reply_wakes.exchange(0, std::memory_order_relaxed),
                 orphan_wait_ends.exchange(0, std::memory_order_relaxed),
                 nested_wait_begins.exchange(0, std::memory_order_relaxed),
                 malformed_waits.exchange(0, std::memory_order_relaxed),
                 malformed_windows.exchange(0, std::memory_order_relaxed),
                 target_switches.exchange(0, std::memory_order_relaxed));
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ReasonCount = 7;
    static constexpr size_t SvcCount = 256;

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

    void ResetCounters() noexcept {
        windows.store(0, std::memory_order_relaxed);
        window_ns.store(0, std::memory_order_relaxed);
        window_max_ns.store(0, std::memory_order_relaxed);
        wait_begins.store(0, std::memory_order_relaxed);
        wait_ends.store(0, std::memory_order_relaxed);
        ignored_candidate_reply_wakes.store(0, std::memory_order_relaxed);
        orphan_wait_ends.store(0, std::memory_order_relaxed);
        nested_wait_begins.store(0, std::memory_order_relaxed);
        malformed_waits.store(0, std::memory_order_relaxed);
        malformed_windows.store(0, std::memory_order_relaxed);
        target_switches.store(0, std::memory_order_relaxed);
        for (auto& value : reason_count) value.store(0, std::memory_order_relaxed);
        for (auto& value : reason_ns) value.store(0, std::memory_order_relaxed);
        for (auto& value : reason_max_ns) value.store(0, std::memory_order_relaxed);
        for (auto& value : svc_count) value.store(0, std::memory_order_relaxed);
        for (auto& value : svc_ns) value.store(0, std::memory_order_relaxed);
        for (auto& value : svc_max_ns) value.store(0, std::memory_order_relaxed);
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> target_tid{0};
    std::atomic<bool> window_open{false};
    std::atomic<u64> window_start_ns{0};
    std::atomic<u64> wait_start_ns{0};
    std::atomic<u32> wait_start_svc{0};
    std::atomic<bool> ignore_reply_wake{false};
    std::atomic<u64> frame_id{0};

    std::atomic<u64> windows{0};
    std::atomic<u64> window_ns{0};
    std::atomic<u64> window_max_ns{0};
    std::array<std::atomic<u64>, ReasonCount> reason_count{};
    std::array<std::atomic<u64>, ReasonCount> reason_ns{};
    std::array<std::atomic<u64>, ReasonCount> reason_max_ns{};
    std::array<std::atomic<u64>, SvcCount> svc_count{};
    std::array<std::atomic<u64>, SvcCount> svc_ns{};
    std::array<std::atomic<u64>, SvcCount> svc_max_ns{};
    std::atomic<u64> wait_begins{0};
    std::atomic<u64> wait_ends{0};
    std::atomic<u64> ignored_candidate_reply_wakes{0};
    std::atomic<u64> orphan_wait_ends{0};
    std::atomic<u64> nested_wait_begins{0};
    std::atomic<u64> malformed_waits{0};
    std::atomic<u64> malformed_windows{0};
    std::atomic<u64> target_switches{0};

    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace Core
