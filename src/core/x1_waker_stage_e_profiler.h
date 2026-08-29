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
#include "core/x1_waker_stage_d_profiler.h"

namespace Core {

class X1WakerStageEProfiler final {
public:
    using Clock = std::chrono::steady_clock;

    struct CallToken {
        bool active{};
        bool owns_active_wait{};
        bool promoted_at_begin{};
        u32 slot{InvalidSlot};
        u64 address{};
        u64 start_ns{};
    };

    static X1WakerStageEProfiler& Get() {
        static X1WakerStageEProfiler profiler;
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
        promoted_address.store(0, std::memory_order_relaxed);
        promoted_switches.store(0, std::memory_order_relaxed);
        wait_slot_overflow.store(0, std::memory_order_relaxed);
        signal_slot_overflow.store(0, std::memory_order_relaxed);
        nested_wait.store(0, std::memory_order_relaxed);
        malformed_wait.store(0, std::memory_order_relaxed);
        signal_calls.store(0, std::memory_order_relaxed);
        signal_no_active.store(0, std::memory_order_relaxed);
        promoted_wait_done.store(0, std::memory_order_relaxed);
        promoted_wait_no_signal.store(0, std::memory_order_relaxed);
        active_wait_start_ns.store(0, std::memory_order_relaxed);
        active_wait_address.store(0, std::memory_order_relaxed);
        active_wait_promoted.store(false, std::memory_order_relaxed);
        active_signal_ns.store(0, std::memory_order_relaxed);
        active_signal_slot.store(InvalidSlot, std::memory_order_relaxed);
        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;

        for (auto& slot : wait_slots) {
            slot.address.store(0, std::memory_order_relaxed);
            slot.arbitration_type.store(0, std::memory_order_relaxed);
            slot.ref_value.store(0, std::memory_order_relaxed);
            slot.ref_timeout_ns.store(0, std::memory_order_relaxed);
            slot.value_var.store(0, std::memory_order_relaxed);
            slot.timeout_var.store(0, std::memory_order_relaxed);
            slot.calls.store(0, std::memory_order_relaxed);
            slot.completed.store(0, std::memory_order_relaxed);
            slot.total_ns.store(0, std::memory_order_relaxed);
            slot.max_ns.store(0, std::memory_order_relaxed);
            slot.ok.store(0, std::memory_order_relaxed);
            slot.timed_out.store(0, std::memory_order_relaxed);
            slot.other.store(0, std::memory_order_relaxed);
        }
        for (auto& slot : signal_slots) {
            slot.thread_id.store(0, std::memory_order_relaxed);
            slot.signal_type.store(0, std::memory_order_relaxed);
            slot.ref_value.store(0, std::memory_order_relaxed);
            slot.ref_count.store(0, std::memory_order_relaxed);
            slot.value_var.store(0, std::memory_order_relaxed);
            slot.count_var.store(0, std::memory_order_relaxed);
            slot.calls.store(0, std::memory_order_relaxed);
            slot.during_wait.store(0, std::memory_order_relaxed);
            slot.w2s_total_ns.store(0, std::memory_order_relaxed);
            slot.w2s_max_ns.store(0, std::memory_order_relaxed);
            slot.s2e_count.store(0, std::memory_order_relaxed);
            slot.s2e_total_ns.store(0, std::memory_order_relaxed);
            slot.s2e_max_ns.store(0, std::memory_order_relaxed);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    [[nodiscard]] bool ShouldTrackPromotedSignalAddress(u64 address) const noexcept {
        const u64 promoted = promoted_address.load(std::memory_order_acquire);
        return Enabled() && promoted != 0 && address == promoted;
    }

    CallToken BeginWait(u64 thread_id, u64 address, u32 arbitration_type, s32 value,
                        s64 timeout_ns) noexcept {
        if (!Enabled() || !X1WakerStageDProfiler::Get().ShouldTrackThread(thread_id)) {
            return {};
        }

        waker_tid.store(thread_id, std::memory_order_relaxed);
        const u32 slot_index = FindOrClaimWaitSlot(address, arbitration_type, value, timeout_ns);
        if (slot_index == InvalidSlot) {
            wait_slot_overflow.fetch_add(1, std::memory_order_relaxed);
            return {};
        }

        auto& slot = wait_slots[slot_index];
        slot.calls.fetch_add(1, std::memory_order_relaxed);
        if (slot.ref_value.load(std::memory_order_relaxed) != value) {
            slot.value_var.fetch_add(1, std::memory_order_relaxed);
        }
        if (slot.ref_timeout_ns.load(std::memory_order_relaxed) != timeout_ns) {
            slot.timeout_var.fetch_add(1, std::memory_order_relaxed);
        }

        const u64 now_ns = NowNs();
        u64 expected = 0;
        const bool owns_active = active_wait_start_ns.compare_exchange_strong(
            expected, now_ns, std::memory_order_acq_rel, std::memory_order_relaxed);
        const bool promoted = address == promoted_address.load(std::memory_order_acquire) &&
                              address != 0;
        if (owns_active) {
            active_wait_address.store(address, std::memory_order_release);
            active_wait_promoted.store(promoted, std::memory_order_release);
            active_signal_ns.store(0, std::memory_order_release);
            active_signal_slot.store(InvalidSlot, std::memory_order_release);
        } else {
            nested_wait.fetch_add(1, std::memory_order_relaxed);
        }

        return CallToken{true, owns_active, promoted, slot_index, address, now_ns};
    }

    void EndWait(const CallToken& token, bool success, bool timed_out) noexcept {
        if (!token.active || token.slot >= WaitSlotCount) {
            return;
        }

        const u64 now_ns = NowNs();
        if (now_ns < token.start_ns) {
            malformed_wait.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        const u64 duration_ns = now_ns - token.start_ns;
        auto& slot = wait_slots[token.slot];
        slot.completed.fetch_add(1, std::memory_order_relaxed);
        slot.total_ns.fetch_add(duration_ns, std::memory_order_relaxed);
        AtomicMax(slot.max_ns, duration_ns);
        if (success) {
            slot.ok.fetch_add(1, std::memory_order_relaxed);
        } else if (timed_out) {
            slot.timed_out.fetch_add(1, std::memory_order_relaxed);
        } else {
            slot.other.fetch_add(1, std::memory_order_relaxed);
        }

        if (!token.owns_active_wait) {
            return;
        }

        const u64 active_start = active_wait_start_ns.load(std::memory_order_acquire);
        const u64 active_address_now = active_wait_address.load(std::memory_order_acquire);
        if (active_start != token.start_ns || active_address_now != token.address) {
            malformed_wait.fetch_add(1, std::memory_order_relaxed);
            active_wait_start_ns.store(0, std::memory_order_release);
            active_wait_address.store(0, std::memory_order_release);
            active_wait_promoted.store(false, std::memory_order_release);
            active_signal_ns.store(0, std::memory_order_release);
            active_signal_slot.store(InvalidSlot, std::memory_order_release);
            return;
        }

        if (token.promoted_at_begin) {
            promoted_wait_done.fetch_add(1, std::memory_order_relaxed);
            const u64 signal_ns = active_signal_ns.load(std::memory_order_acquire);
            const u32 signal_slot = active_signal_slot.load(std::memory_order_acquire);
            if (signal_ns != 0 && signal_ns <= now_ns && signal_slot < SignalSlotCount) {
                const u64 s2e_ns = now_ns - signal_ns;
                auto& owner = signal_slots[signal_slot];
                owner.s2e_count.fetch_add(1, std::memory_order_relaxed);
                owner.s2e_total_ns.fetch_add(s2e_ns, std::memory_order_relaxed);
                AtomicMax(owner.s2e_max_ns, s2e_ns);
            } else {
                promoted_wait_no_signal.fetch_add(1, std::memory_order_relaxed);
            }
        }

        active_wait_start_ns.store(0, std::memory_order_release);
        active_wait_address.store(0, std::memory_order_release);
        active_wait_promoted.store(false, std::memory_order_release);
        active_signal_ns.store(0, std::memory_order_release);
        active_signal_slot.store(InvalidSlot, std::memory_order_release);
    }

    void RecordSignal(u64 thread_id, u64 address, u32 signal_type, s32 value,
                      s32 count) noexcept {
        if (!ShouldTrackPromotedSignalAddress(address)) {
            return;
        }

        signal_calls.fetch_add(1, std::memory_order_relaxed);
        const u32 slot_index = FindOrClaimSignalSlot(thread_id, signal_type, value, count);
        if (slot_index == InvalidSlot) {
            signal_slot_overflow.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        auto& slot = signal_slots[slot_index];
        slot.calls.fetch_add(1, std::memory_order_relaxed);
        if (slot.ref_value.load(std::memory_order_relaxed) != value) {
            slot.value_var.fetch_add(1, std::memory_order_relaxed);
        }
        if (slot.ref_count.load(std::memory_order_relaxed) != count) {
            slot.count_var.fetch_add(1, std::memory_order_relaxed);
        }

        const u64 start_ns = active_wait_start_ns.load(std::memory_order_acquire);
        const u64 active_address_now = active_wait_address.load(std::memory_order_acquire);
        const bool active_promoted_now = active_wait_promoted.load(std::memory_order_acquire);
        if (start_ns == 0 || active_address_now != address || !active_promoted_now) {
            signal_no_active.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        const u64 now_ns = NowNs();
        if (now_ns < start_ns) {
            malformed_wait.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        const u64 w2s_ns = now_ns - start_ns;
        slot.during_wait.fetch_add(1, std::memory_order_relaxed);
        slot.w2s_total_ns.fetch_add(w2s_ns, std::memory_order_relaxed);
        AtomicMax(slot.w2s_max_ns, w2s_ns);
        active_signal_ns.store(now_ns, std::memory_order_release);
        active_signal_slot.store(slot_index, std::memory_order_release);
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

        std::array<WaitSnapshot, WaitSlotCount> wait_snapshot{};
        u64 wait_calls = 0;
        u64 wait_done = 0;
        u64 wait_total_ns = 0;
        for (size_t i = 0; i < WaitSlotCount; ++i) {
            auto& slot = wait_slots[i];
            auto& snap = wait_snapshot[i];
            snap.address = slot.address.load(std::memory_order_relaxed);
            snap.arbitration_type = slot.arbitration_type.load(std::memory_order_relaxed);
            snap.ref_value = slot.ref_value.load(std::memory_order_relaxed);
            snap.ref_timeout_ns = slot.ref_timeout_ns.load(std::memory_order_relaxed);
            snap.value_var = slot.value_var.exchange(0, std::memory_order_relaxed);
            snap.timeout_var = slot.timeout_var.exchange(0, std::memory_order_relaxed);
            snap.calls = slot.calls.exchange(0, std::memory_order_relaxed);
            snap.completed = slot.completed.exchange(0, std::memory_order_relaxed);
            snap.total_ns = slot.total_ns.exchange(0, std::memory_order_relaxed);
            snap.max_ns = slot.max_ns.exchange(0, std::memory_order_relaxed);
            snap.ok = slot.ok.exchange(0, std::memory_order_relaxed);
            snap.timed_out = slot.timed_out.exchange(0, std::memory_order_relaxed);
            snap.other = slot.other.exchange(0, std::memory_order_relaxed);
            wait_calls += snap.calls;
            wait_done += snap.completed;
            wait_total_ns += snap.total_ns;
        }

        std::array<u32, TopWaitCount> top_wait{};
        for (auto& index : top_wait) {
            index = InvalidSlot;
        }
        SelectTopWaits(wait_snapshot, top_wait);

        const u64 current_promoted = promoted_address.load(std::memory_order_acquire);
        u64 next_promoted = current_promoted;
        if (top_wait[0] != InvalidSlot && wait_snapshot[top_wait[0]].total_ns != 0) {
            next_promoted = wait_snapshot[top_wait[0]].address;
            if (next_promoted != 0 && next_promoted != current_promoted) {
                promoted_address.store(next_promoted, std::memory_order_release);
                promoted_switches.fetch_add(1, std::memory_order_relaxed);
            }
        }

        std::array<SignalSnapshot, SignalSlotCount> signal_snapshot{};
        for (size_t i = 0; i < SignalSlotCount; ++i) {
            auto& slot = signal_slots[i];
            auto& snap = signal_snapshot[i];
            snap.thread_id = slot.thread_id.load(std::memory_order_relaxed);
            snap.signal_type = slot.signal_type.load(std::memory_order_relaxed);
            snap.ref_value = slot.ref_value.load(std::memory_order_relaxed);
            snap.ref_count = slot.ref_count.load(std::memory_order_relaxed);
            snap.value_var = slot.value_var.exchange(0, std::memory_order_relaxed);
            snap.count_var = slot.count_var.exchange(0, std::memory_order_relaxed);
            snap.calls = slot.calls.exchange(0, std::memory_order_relaxed);
            snap.during_wait = slot.during_wait.exchange(0, std::memory_order_relaxed);
            snap.w2s_total_ns = slot.w2s_total_ns.exchange(0, std::memory_order_relaxed);
            snap.w2s_max_ns = slot.w2s_max_ns.exchange(0, std::memory_order_relaxed);
            snap.s2e_count = slot.s2e_count.exchange(0, std::memory_order_relaxed);
            snap.s2e_total_ns = slot.s2e_total_ns.exchange(0, std::memory_order_relaxed);
            snap.s2e_max_ns = slot.s2e_max_ns.exchange(0, std::memory_order_relaxed);
        }

        std::array<u32, TopSignalCount> top_signal{};
        for (auto& index : top_signal) {
            index = InvalidSlot;
        }
        SelectTopSignals(signal_snapshot, top_signal);

        const auto top0 = GetWaitSnapshot(wait_snapshot, top_wait[0]);
        const auto top1 = GetWaitSnapshot(wait_snapshot, top_wait[1]);
        const auto top2 = GetWaitSnapshot(wait_snapshot, top_wait[2]);
        const auto top3 = GetWaitSnapshot(wait_snapshot, top_wait[3]);
        const auto sig0 = GetSignalSnapshot(signal_snapshot, top_signal[0]);
        const auto sig1 = GetSignalSnapshot(signal_snapshot, top_signal[1]);
        const auto sig2 = GetSignalSnapshot(signal_snapshot, top_signal[2]);
        const auto sig3 = GetSignalSnapshot(signal_snapshot, top_signal[3]);

        LOG_INFO(HW_GPU,
                 "[X1-WAKERE] frame={} frames={} wakerTid={:#x} waits={} done={} wait={:.3f}ms "
                 "promoted={:#x} nextPromoted={:#x} promotedSwitch={} "
                 "top0={:#x}/t{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/v{}/tns{}/vvar{}/tvar{}/ok{}/to{}/other{} "
                 "top1={:#x}/t{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/v{}/tns{}/vvar{}/tvar{}/ok{}/to{}/other{} "
                 "top2={:#x}/t{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/v{}/tns{}/vvar{}/tvar{}/ok{}/to{}/other{} "
                 "top3={:#x}/t{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/v{}/tns{}/vvar{}/tvar{}/ok{}/to{}/other{} "
                 "sigCalls={} noActive={} promotedWaitDone={} noSignalReturn={} "
                 "sig0={:#x}/t{}/{}x/during{}/w2s{:.3f}avg/{:.3f}max/s2e{:.3f}avg/{:.3f}max/v{}/cnt{}/vvar{}/cvar{} "
                 "sig1={:#x}/t{}/{}x/during{}/w2s{:.3f}avg/{:.3f}max/s2e{:.3f}avg/{:.3f}max/v{}/cnt{}/vvar{}/cvar{} "
                 "sig2={:#x}/t{}/{}x/during{}/w2s{:.3f}avg/{:.3f}max/s2e{:.3f}avg/{:.3f}max/v{}/cnt{}/vvar{}/cvar{} "
                 "sig3={:#x}/t{}/{}x/during{}/w2s{:.3f}avg/{:.3f}max/s2e{:.3f}avg/{:.3f}max/v{}/cnt{}/vvar{}/cvar{} "
                 "waitOverflow={} signalOverflow={} nestedWait={} malformedWait={}",
                 frame, frames, waker_tid.load(std::memory_order_relaxed), wait_calls, wait_done,
                 ToMs(wait_total_ns), current_promoted, next_promoted,
                 promoted_switches.exchange(0, std::memory_order_relaxed),
                 top0.address, top0.arbitration_type, top0.calls, top0.completed, ToMs(top0.total_ns),
                 AvgMs(top0.total_ns, top0.completed), ToMs(top0.max_ns), top0.ref_value,
                 top0.ref_timeout_ns, top0.value_var, top0.timeout_var, top0.ok, top0.timed_out,
                 top0.other, top1.address, top1.arbitration_type, top1.calls, top1.completed,
                 ToMs(top1.total_ns), AvgMs(top1.total_ns, top1.completed), ToMs(top1.max_ns),
                 top1.ref_value, top1.ref_timeout_ns, top1.value_var, top1.timeout_var, top1.ok,
                 top1.timed_out, top1.other, top2.address, top2.arbitration_type, top2.calls,
                 top2.completed, ToMs(top2.total_ns), AvgMs(top2.total_ns, top2.completed),
                 ToMs(top2.max_ns), top2.ref_value, top2.ref_timeout_ns, top2.value_var,
                 top2.timeout_var, top2.ok, top2.timed_out, top2.other, top3.address,
                 top3.arbitration_type, top3.calls, top3.completed, ToMs(top3.total_ns),
                 AvgMs(top3.total_ns, top3.completed), ToMs(top3.max_ns), top3.ref_value,
                 top3.ref_timeout_ns, top3.value_var, top3.timeout_var, top3.ok, top3.timed_out,
                 top3.other, signal_calls.exchange(0, std::memory_order_relaxed),
                 signal_no_active.exchange(0, std::memory_order_relaxed),
                 promoted_wait_done.exchange(0, std::memory_order_relaxed),
                 promoted_wait_no_signal.exchange(0, std::memory_order_relaxed),
                 sig0.thread_id, sig0.signal_type, sig0.calls, sig0.during_wait,
                 AvgMs(sig0.w2s_total_ns, sig0.during_wait), ToMs(sig0.w2s_max_ns),
                 AvgMs(sig0.s2e_total_ns, sig0.s2e_count), ToMs(sig0.s2e_max_ns),
                 sig0.ref_value, sig0.ref_count, sig0.value_var, sig0.count_var,
                 sig1.thread_id, sig1.signal_type, sig1.calls, sig1.during_wait,
                 AvgMs(sig1.w2s_total_ns, sig1.during_wait), ToMs(sig1.w2s_max_ns),
                 AvgMs(sig1.s2e_total_ns, sig1.s2e_count), ToMs(sig1.s2e_max_ns),
                 sig1.ref_value, sig1.ref_count, sig1.value_var, sig1.count_var,
                 sig2.thread_id, sig2.signal_type, sig2.calls, sig2.during_wait,
                 AvgMs(sig2.w2s_total_ns, sig2.during_wait), ToMs(sig2.w2s_max_ns),
                 AvgMs(sig2.s2e_total_ns, sig2.s2e_count), ToMs(sig2.s2e_max_ns),
                 sig2.ref_value, sig2.ref_count, sig2.value_var, sig2.count_var,
                 sig3.thread_id, sig3.signal_type, sig3.calls, sig3.during_wait,
                 AvgMs(sig3.w2s_total_ns, sig3.during_wait), ToMs(sig3.w2s_max_ns),
                 AvgMs(sig3.s2e_total_ns, sig3.s2e_count), ToMs(sig3.s2e_max_ns),
                 sig3.ref_value, sig3.ref_count, sig3.value_var, sig3.count_var,
                 wait_slot_overflow.exchange(0, std::memory_order_relaxed),
                 signal_slot_overflow.exchange(0, std::memory_order_relaxed),
                 nested_wait.exchange(0, std::memory_order_relaxed),
                 malformed_wait.exchange(0, std::memory_order_relaxed));
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr u32 WaitSlotCount = 16;
    static constexpr u32 SignalSlotCount = 8;
    static constexpr u32 TopWaitCount = 4;
    static constexpr u32 TopSignalCount = 4;
    static constexpr u32 InvalidSlot = (std::numeric_limits<u32>::max)();

    struct WaitSlot {
        std::atomic<u64> address{0};
        std::atomic<u32> arbitration_type{0};
        std::atomic<s32> ref_value{0};
        std::atomic<s64> ref_timeout_ns{0};
        std::atomic<u64> value_var{0};
        std::atomic<u64> timeout_var{0};
        std::atomic<u64> calls{0};
        std::atomic<u64> completed{0};
        std::atomic<u64> total_ns{0};
        std::atomic<u64> max_ns{0};
        std::atomic<u64> ok{0};
        std::atomic<u64> timed_out{0};
        std::atomic<u64> other{0};
    };

    struct SignalSlot {
        std::atomic<u64> thread_id{0};
        std::atomic<u32> signal_type{0};
        std::atomic<s32> ref_value{0};
        std::atomic<s32> ref_count{0};
        std::atomic<u64> value_var{0};
        std::atomic<u64> count_var{0};
        std::atomic<u64> calls{0};
        std::atomic<u64> during_wait{0};
        std::atomic<u64> w2s_total_ns{0};
        std::atomic<u64> w2s_max_ns{0};
        std::atomic<u64> s2e_count{0};
        std::atomic<u64> s2e_total_ns{0};
        std::atomic<u64> s2e_max_ns{0};
    };

    struct WaitSnapshot {
        u64 address{};
        u32 arbitration_type{};
        s32 ref_value{};
        s64 ref_timeout_ns{};
        u64 value_var{};
        u64 timeout_var{};
        u64 calls{};
        u64 completed{};
        u64 total_ns{};
        u64 max_ns{};
        u64 ok{};
        u64 timed_out{};
        u64 other{};
    };

    struct SignalSnapshot {
        u64 thread_id{};
        u32 signal_type{};
        s32 ref_value{};
        s32 ref_count{};
        u64 value_var{};
        u64 count_var{};
        u64 calls{};
        u64 during_wait{};
        u64 w2s_total_ns{};
        u64 w2s_max_ns{};
        u64 s2e_count{};
        u64 s2e_total_ns{};
        u64 s2e_max_ns{};
    };

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

    u32 FindOrClaimWaitSlot(u64 address, u32 arbitration_type, s32 value,
                            s64 timeout_ns) noexcept {
        for (u32 i = 0; i < WaitSlotCount; ++i) {
            auto& slot = wait_slots[i];
            if (slot.address.load(std::memory_order_acquire) == address &&
                slot.arbitration_type.load(std::memory_order_relaxed) == arbitration_type) {
                return i;
            }
        }
        for (u32 i = 0; i < WaitSlotCount; ++i) {
            auto& slot = wait_slots[i];
            u64 expected = 0;
            if (slot.address.compare_exchange_strong(expected, address, std::memory_order_acq_rel,
                                                     std::memory_order_relaxed)) {
                slot.arbitration_type.store(arbitration_type, std::memory_order_relaxed);
                slot.ref_value.store(value, std::memory_order_relaxed);
                slot.ref_timeout_ns.store(timeout_ns, std::memory_order_relaxed);
                return i;
            }
            if (expected == address &&
                slot.arbitration_type.load(std::memory_order_relaxed) == arbitration_type) {
                return i;
            }
        }
        return InvalidSlot;
    }

    u32 FindOrClaimSignalSlot(u64 thread_id, u32 signal_type, s32 value, s32 count) noexcept {
        for (u32 i = 0; i < SignalSlotCount; ++i) {
            auto& slot = signal_slots[i];
            if (slot.thread_id.load(std::memory_order_acquire) == thread_id &&
                slot.signal_type.load(std::memory_order_relaxed) == signal_type) {
                return i;
            }
        }
        for (u32 i = 0; i < SignalSlotCount; ++i) {
            auto& slot = signal_slots[i];
            u64 expected = 0;
            if (slot.thread_id.compare_exchange_strong(expected, thread_id,
                                                       std::memory_order_acq_rel,
                                                       std::memory_order_relaxed)) {
                slot.signal_type.store(signal_type, std::memory_order_relaxed);
                slot.ref_value.store(value, std::memory_order_relaxed);
                slot.ref_count.store(count, std::memory_order_relaxed);
                return i;
            }
            if (expected == thread_id &&
                slot.signal_type.load(std::memory_order_relaxed) == signal_type) {
                return i;
            }
        }
        return InvalidSlot;
    }

    static void SelectTopWaits(const std::array<WaitSnapshot, WaitSlotCount>& snapshots,
                               std::array<u32, TopWaitCount>& top) noexcept {
        for (u32 i = 0; i < WaitSlotCount; ++i) {
            if (snapshots[i].total_ns == 0) {
                continue;
            }
            for (u32 pos = 0; pos < TopWaitCount; ++pos) {
                if (top[pos] != InvalidSlot &&
                    snapshots[i].total_ns <= snapshots[top[pos]].total_ns) {
                    continue;
                }
                for (u32 shift = TopWaitCount - 1; shift > pos; --shift) {
                    top[shift] = top[shift - 1];
                }
                top[pos] = i;
                break;
            }
        }
    }

    static void SelectTopSignals(const std::array<SignalSnapshot, SignalSlotCount>& snapshots,
                                 std::array<u32, TopSignalCount>& top) noexcept {
        for (u32 i = 0; i < SignalSlotCount; ++i) {
            if (snapshots[i].during_wait == 0) {
                continue;
            }
            for (u32 pos = 0; pos < TopSignalCount; ++pos) {
                if (top[pos] != InvalidSlot &&
                    snapshots[i].during_wait <= snapshots[top[pos]].during_wait) {
                    continue;
                }
                for (u32 shift = TopSignalCount - 1; shift > pos; --shift) {
                    top[shift] = top[shift - 1];
                }
                top[pos] = i;
                break;
            }
        }
    }

    static WaitSnapshot GetWaitSnapshot(const std::array<WaitSnapshot, WaitSlotCount>& snapshots,
                                        u32 index) noexcept {
        return index < WaitSlotCount ? snapshots[index] : WaitSnapshot{};
    }

    static SignalSnapshot GetSignalSnapshot(
        const std::array<SignalSnapshot, SignalSlotCount>& snapshots, u32 index) noexcept {
        return index < SignalSlotCount ? snapshots[index] : SignalSnapshot{};
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> waker_tid{0};
    std::atomic<u64> promoted_address{0};
    std::atomic<u64> promoted_switches{0};
    std::array<WaitSlot, WaitSlotCount> wait_slots{};
    std::array<SignalSlot, SignalSlotCount> signal_slots{};

    std::atomic<u64> wait_slot_overflow{0};
    std::atomic<u64> signal_slot_overflow{0};
    std::atomic<u64> nested_wait{0};
    std::atomic<u64> malformed_wait{0};

    std::atomic<u64> active_wait_start_ns{0};
    std::atomic<u64> active_wait_address{0};
    std::atomic<bool> active_wait_promoted{false};
    std::atomic<u64> active_signal_ns{0};
    std::atomic<u32> active_signal_slot{InvalidSlot};

    std::atomic<u64> signal_calls{0};
    std::atomic<u64> signal_no_active{0};
    std::atomic<u64> promoted_wait_done{0};
    std::atomic<u64> promoted_wait_no_signal{0};

    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
};

} // namespace Core
