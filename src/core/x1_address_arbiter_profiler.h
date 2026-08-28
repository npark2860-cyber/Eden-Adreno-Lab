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

class X1AddressArbiterProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    struct CallToken {
        u64 start_ns{};
        u32 slot{};
        bool active{};
    };

    static X1AddressArbiterProfiler& Get() {
        static X1AddressArbiterProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_address_arbiter_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        armed.store(false, std::memory_order_relaxed);
        target_tid.store(0, std::memory_order_relaxed);
        target_switches.store(0, std::memory_order_relaxed);
        slot_overflow.store(0, std::memory_order_relaxed);
        frame_id.store(0, std::memory_order_relaxed);
        signal_slot_overflow.store(0, std::memory_order_relaxed);
        target_wait_start_ns.store(0, std::memory_order_relaxed);
        target_wait_tid.store(0, std::memory_order_relaxed);
        wait_begun.store(0, std::memory_order_relaxed);
        wait_done.store(0, std::memory_order_relaxed);
        wait_matched_signal.store(0, std::memory_order_relaxed);
        wait_missing_signal.store(0, std::memory_order_relaxed);
        signals_without_wait.store(0, std::memory_order_relaxed);
        latest_signal_ns.store(0, std::memory_order_relaxed);
        latest_signal_slot.store(0, std::memory_order_relaxed);
        frames_since_report = 0;
        report_start = Clock::now();
        for (auto& slot : slots) {
            slot.address_key.store(0, std::memory_order_relaxed);
            slot.type.store(0, std::memory_order_relaxed);
            slot.timeout_ref_ns.store(0, std::memory_order_relaxed);
            slot.ResetCounters();
        }
        for (auto& slot : signal_slots) {
            slot.thread_key.store(0, std::memory_order_relaxed);
            slot.type.store(0, std::memory_order_relaxed);
            slot.value_ref.store(0, std::memory_order_relaxed);
            slot.count_ref.store(0, std::memory_order_relaxed);
            slot.ResetCounters();
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    [[nodiscard]] bool ShouldTrackSignalAddress(u64 address) const noexcept {
        return Enabled() && armed.load(std::memory_order_acquire) && address == TargetSignalAddress;
    }

    CallToken BeginCall(u64 thread_id, u64 address, u32 arbitration_type,
                        s64 timeout_ns) noexcept {
        if (!Enabled() || !armed.load(std::memory_order_acquire) || thread_id == 0) {
            return {};
        }

        const u64 tracked = target_tid.load(std::memory_order_acquire);
        if (tracked != 0 && tracked != thread_id) {
            target_switches.fetch_add(1, std::memory_order_relaxed);
        }
        target_tid.store(thread_id, std::memory_order_release);

        const u32 slot_index = FindOrClaimSlot(address, arbitration_type, timeout_ns);
        if (slot_index >= SlotCount) {
            slot_overflow.fetch_add(1, std::memory_order_relaxed);
            return {};
        }

        auto& slot = slots[slot_index];
        slot.calls.fetch_add(1, std::memory_order_relaxed);
        slot.inflight.fetch_add(1, std::memory_order_relaxed);

        const s64 timeout_ref = slot.timeout_ref_ns.load(std::memory_order_acquire);
        if (timeout_ref != timeout_ns) {
            slot.timeout_mismatch.fetch_add(1, std::memory_order_relaxed);
        }

        return CallToken{NowNs(), slot_index, true};
    }

    void BeginTargetWait(u64 thread_id, u64 address, u64 start_ns) noexcept {
        if (!ShouldTrackSignalAddress(address) || thread_id == 0 || start_ns == 0) {
            return;
        }
        target_wait_tid.store(thread_id, std::memory_order_release);
        target_wait_start_ns.store(start_ns, std::memory_order_release);
        wait_begun.fetch_add(1, std::memory_order_relaxed);
    }

    void EndTargetWait(u64 thread_id, u64 address, u64 start_ns) noexcept {
        if (!ShouldTrackSignalAddress(address) || thread_id == 0 || start_ns == 0) {
            return;
        }

        const u64 end_ns = NowNs();
        wait_done.fetch_add(1, std::memory_order_relaxed);

        const u64 signal_ns = latest_signal_ns.load(std::memory_order_acquire);
        const u32 encoded_slot = latest_signal_slot.load(std::memory_order_relaxed);
        if (signal_ns >= start_ns && signal_ns <= end_ns && encoded_slot != 0 &&
            encoded_slot <= SignalSlotCount) {
            wait_matched_signal.fetch_add(1, std::memory_order_relaxed);
            auto& signal_slot = signal_slots[encoded_slot - 1];
            const u64 signal_to_end_ns = end_ns - signal_ns;
            signal_slot.matched_waits.fetch_add(1, std::memory_order_relaxed);
            signal_slot.signal_to_wait_end_total_ns.fetch_add(signal_to_end_ns,
                                                               std::memory_order_relaxed);
            AtomicMax(signal_slot.signal_to_wait_end_max_ns, signal_to_end_ns);
        } else {
            wait_missing_signal.fetch_add(1, std::memory_order_relaxed);
        }

        u64 expected = start_ns;
        target_wait_start_ns.compare_exchange_strong(expected, 0, std::memory_order_acq_rel,
                                                     std::memory_order_relaxed);
    }

    void RecordSignal(u64 thread_id, u64 address, u32 signal_type, s32 value, s32 count) noexcept {
        if (!ShouldTrackSignalAddress(address) || thread_id == 0) {
            return;
        }

        const u32 slot_index = FindOrClaimSignalSlot(thread_id, signal_type, value, count);
        if (slot_index >= SignalSlotCount) {
            signal_slot_overflow.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        const u64 now_ns = NowNs();
        auto& slot = signal_slots[slot_index];
        slot.calls.fetch_add(1, std::memory_order_relaxed);

        if (slot.value_ref.load(std::memory_order_acquire) != value) {
            slot.value_mismatch.fetch_add(1, std::memory_order_relaxed);
        }
        if (slot.count_ref.load(std::memory_order_acquire) != count) {
            slot.count_mismatch.fetch_add(1, std::memory_order_relaxed);
        }

        const u64 wait_start_ns = target_wait_start_ns.load(std::memory_order_acquire);
        if (wait_start_ns != 0 && now_ns >= wait_start_ns) {
            const u64 wait_to_signal_ns = now_ns - wait_start_ns;
            slot.during_wait.fetch_add(1, std::memory_order_relaxed);
            slot.wait_to_signal_total_ns.fetch_add(wait_to_signal_ns, std::memory_order_relaxed);
            AtomicMax(slot.wait_to_signal_max_ns, wait_to_signal_ns);
        } else {
            signals_without_wait.fetch_add(1, std::memory_order_relaxed);
        }

        latest_signal_slot.store(slot_index + 1, std::memory_order_relaxed);
        latest_signal_ns.store(now_ns, std::memory_order_release);
    }

    void EndCall(const CallToken& token, bool success, bool timed_out) noexcept {
        if (!token.active || token.slot >= SlotCount) {
            return;
        }

        const u64 now_ns = NowNs();
        auto& slot = slots[token.slot];
        slot.inflight.fetch_sub(1, std::memory_order_relaxed);
        slot.completed.fetch_add(1, std::memory_order_relaxed);

        if (success) {
            slot.success.fetch_add(1, std::memory_order_relaxed);
        } else if (timed_out) {
            slot.timed_out.fetch_add(1, std::memory_order_relaxed);
        } else {
            slot.other_result.fetch_add(1, std::memory_order_relaxed);
        }

        if (now_ns < token.start_ns) {
            slot.malformed.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        const u64 elapsed_ns = now_ns - token.start_ns;
        slot.total_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
        AtomicMax(slot.max_ns, elapsed_ns);
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

        struct Snapshot {
            u64 address{};
            u32 type{};
            s64 timeout_ref_ns{};
            u64 calls{};
            u64 completed{};
            u64 success{};
            u64 timed_out{};
            u64 other{};
            u64 total_ns{};
            u64 max_ns{};
            u64 timeout_mismatch{};
            u64 malformed{};
            u64 inflight{};
        };

        std::array<Snapshot, SlotCount> snapshots{};
        u64 total_calls{};
        u64 total_completed{};
        u64 total_ns{};
        u64 active_slots{};

        for (u32 i = 0; i < SlotCount; ++i) {
            auto& slot = slots[i];
            Snapshot snap{};
            const u64 encoded_address = slot.address_key.load(std::memory_order_acquire);
            if (encoded_address != 0) {
                snap.address = encoded_address - 1;
                snap.type = slot.type.load(std::memory_order_acquire);
                snap.timeout_ref_ns = slot.timeout_ref_ns.load(std::memory_order_acquire);
            }
            snap.calls = slot.calls.exchange(0, std::memory_order_relaxed);
            snap.completed = slot.completed.exchange(0, std::memory_order_relaxed);
            snap.success = slot.success.exchange(0, std::memory_order_relaxed);
            snap.timed_out = slot.timed_out.exchange(0, std::memory_order_relaxed);
            snap.other = slot.other_result.exchange(0, std::memory_order_relaxed);
            snap.total_ns = slot.total_ns.exchange(0, std::memory_order_relaxed);
            snap.max_ns = slot.max_ns.exchange(0, std::memory_order_relaxed);
            snap.timeout_mismatch = slot.timeout_mismatch.exchange(0, std::memory_order_relaxed);
            snap.malformed = slot.malformed.exchange(0, std::memory_order_relaxed);
            snap.inflight = slot.inflight.load(std::memory_order_relaxed);

            total_calls += snap.calls;
            total_completed += snap.completed;
            total_ns += snap.total_ns;
            if (snap.calls != 0 || snap.completed != 0 || snap.total_ns != 0 || snap.inflight != 0) {
                ++active_slots;
            }
            snapshots[i] = snap;
        }

        std::sort(snapshots.begin(), snapshots.end(), [](const Snapshot& lhs, const Snapshot& rhs) {
            if (lhs.total_ns != rhs.total_ns) {
                return lhs.total_ns > rhs.total_ns;
            }
            return lhs.calls > rhs.calls;
        });

        const auto& a = snapshots[0];
        const auto& b = snapshots[1];
        const auto& c = snapshots[2];
        const auto& d = snapshots[3];

        LOG_INFO(HW_GPU,
                 "[X1-ADDRARB] frame={} frames={} wall={:.3f}ms tid={:#x} slots={} calls={} "
                 "done={} total={:.3f}ms avg={:.3f}ms overflow={} targetSwitch={} "
                 "top0={:#x}/{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/ok{}/to{}/other{}/tns{}/tvar{}/in{} "
                 "top1={:#x}/{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/ok{}/to{}/other{}/tns{}/tvar{}/in{} "
                 "top2={:#x}/{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/ok{}/to{}/other{}/tns{}/tvar{}/in{} "
                 "top3={:#x}/{}/{}x/{}done/{:.3f}ms/{:.3f}avg/{:.3f}max/ok{}/to{}/other{}/tns{}/tvar{}/in{}",
                 frame, frames, ToMs(wall_ns), target_tid.load(std::memory_order_relaxed), active_slots,
                 total_calls, total_completed, ToMs(total_ns), AvgMs(total_ns, total_completed),
                 slot_overflow.exchange(0, std::memory_order_relaxed),
                 target_switches.exchange(0, std::memory_order_relaxed),
                 a.address, TypeName(a.type), a.calls, a.completed, ToMs(a.total_ns),
                 AvgMs(a.total_ns, a.completed), ToMs(a.max_ns), a.success, a.timed_out, a.other,
                 a.timeout_ref_ns, a.timeout_mismatch, a.inflight,
                 b.address, TypeName(b.type), b.calls, b.completed, ToMs(b.total_ns),
                 AvgMs(b.total_ns, b.completed), ToMs(b.max_ns), b.success, b.timed_out, b.other,
                 b.timeout_ref_ns, b.timeout_mismatch, b.inflight,
                 c.address, TypeName(c.type), c.calls, c.completed, ToMs(c.total_ns),
                 AvgMs(c.total_ns, c.completed), ToMs(c.max_ns), c.success, c.timed_out, c.other,
                 c.timeout_ref_ns, c.timeout_mismatch, c.inflight,
                 d.address, TypeName(d.type), d.calls, d.completed, ToMs(d.total_ns),
                 AvgMs(d.total_ns, d.completed), ToMs(d.max_ns), d.success, d.timed_out, d.other,
                 d.timeout_ref_ns, d.timeout_mismatch, d.inflight);

        ReportSignals(frame, frames);
        armed.store(true, std::memory_order_release);
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr u32 SlotCount = 8;
    static constexpr u32 SignalSlotCount = 8;
    static constexpr u64 TargetSignalAddress = 0x210adbc120ULL;

    struct Slot {
        std::atomic<u64> address_key{0};
        std::atomic<u32> type{0};
        std::atomic<s64> timeout_ref_ns{0};
        std::atomic<u64> calls{0};
        std::atomic<u64> completed{0};
        std::atomic<u64> success{0};
        std::atomic<u64> timed_out{0};
        std::atomic<u64> other_result{0};
        std::atomic<u64> total_ns{0};
        std::atomic<u64> max_ns{0};
        std::atomic<u64> timeout_mismatch{0};
        std::atomic<u64> malformed{0};
        std::atomic<u64> inflight{0};

        void ResetCounters() noexcept {
            calls.store(0, std::memory_order_relaxed);
            completed.store(0, std::memory_order_relaxed);
            success.store(0, std::memory_order_relaxed);
            timed_out.store(0, std::memory_order_relaxed);
            other_result.store(0, std::memory_order_relaxed);
            total_ns.store(0, std::memory_order_relaxed);
            max_ns.store(0, std::memory_order_relaxed);
            timeout_mismatch.store(0, std::memory_order_relaxed);
            malformed.store(0, std::memory_order_relaxed);
            inflight.store(0, std::memory_order_relaxed);
        }
    };

    struct SignalSlot {
        std::atomic<u64> thread_key{0};
        std::atomic<u32> type{0};
        std::atomic<s32> value_ref{0};
        std::atomic<s32> count_ref{0};
        std::atomic<u64> calls{0};
        std::atomic<u64> value_mismatch{0};
        std::atomic<u64> count_mismatch{0};
        std::atomic<u64> during_wait{0};
        std::atomic<u64> wait_to_signal_total_ns{0};
        std::atomic<u64> wait_to_signal_max_ns{0};
        std::atomic<u64> matched_waits{0};
        std::atomic<u64> signal_to_wait_end_total_ns{0};
        std::atomic<u64> signal_to_wait_end_max_ns{0};

        void ResetCounters() noexcept {
            calls.store(0, std::memory_order_relaxed);
            value_mismatch.store(0, std::memory_order_relaxed);
            count_mismatch.store(0, std::memory_order_relaxed);
            during_wait.store(0, std::memory_order_relaxed);
            wait_to_signal_total_ns.store(0, std::memory_order_relaxed);
            wait_to_signal_max_ns.store(0, std::memory_order_relaxed);
            matched_waits.store(0, std::memory_order_relaxed);
            signal_to_wait_end_total_ns.store(0, std::memory_order_relaxed);
            signal_to_wait_end_max_ns.store(0, std::memory_order_relaxed);
        }
    };

    struct SignalSnapshot {
        u64 thread_id{};
        u32 type{};
        s32 value_ref{};
        s32 count_ref{};
        u64 calls{};
        u64 value_mismatch{};
        u64 count_mismatch{};
        u64 during_wait{};
        u64 wait_to_signal_total_ns{};
        u64 wait_to_signal_max_ns{};
        u64 matched_waits{};
        u64 signal_to_wait_end_total_ns{};
        u64 signal_to_wait_end_max_ns{};
    };

    u32 FindOrClaimSlot(u64 address, u32 arbitration_type, s64 timeout_ns) noexcept {
        const u64 key = address + 1;
        for (u32 i = 0; i < SlotCount; ++i) {
            auto& slot = slots[i];
            const u64 existing = slot.address_key.load(std::memory_order_acquire);
            if (existing == key && slot.type.load(std::memory_order_acquire) == arbitration_type) {
                return i;
            }
            if (existing != 0) {
                continue;
            }

            u64 expected = 0;
            if (slot.address_key.compare_exchange_strong(expected, key, std::memory_order_acq_rel,
                                                         std::memory_order_relaxed)) {
                slot.type.store(arbitration_type, std::memory_order_release);
                slot.timeout_ref_ns.store(timeout_ns, std::memory_order_release);
                return i;
            }
        }
        return SlotCount;
    }

    u32 FindOrClaimSignalSlot(u64 thread_id, u32 signal_type, s32 value, s32 count) noexcept {
        const u64 key = thread_id + 1;
        for (u32 i = 0; i < SignalSlotCount; ++i) {
            auto& slot = signal_slots[i];
            const u64 existing = slot.thread_key.load(std::memory_order_acquire);
            if (existing == key && slot.type.load(std::memory_order_acquire) == signal_type) {
                return i;
            }
            if (existing != 0) {
                continue;
            }

            u64 expected = 0;
            if (slot.thread_key.compare_exchange_strong(expected, key, std::memory_order_acq_rel,
                                                        std::memory_order_relaxed)) {
                slot.type.store(signal_type, std::memory_order_release);
                slot.value_ref.store(value, std::memory_order_release);
                slot.count_ref.store(count, std::memory_order_release);
                return i;
            }
        }
        return SignalSlotCount;
    }

    void ReportSignals(u64 frame, u64 frames) {
        std::array<SignalSnapshot, SignalSlotCount> snapshots{};
        u64 total_calls{};
        u64 active_slots{};

        for (u32 i = 0; i < SignalSlotCount; ++i) {
            auto& slot = signal_slots[i];
            SignalSnapshot snap{};
            const u64 encoded_thread = slot.thread_key.load(std::memory_order_acquire);
            if (encoded_thread != 0) {
                snap.thread_id = encoded_thread - 1;
                snap.type = slot.type.load(std::memory_order_acquire);
                snap.value_ref = slot.value_ref.load(std::memory_order_acquire);
                snap.count_ref = slot.count_ref.load(std::memory_order_acquire);
            }
            snap.calls = slot.calls.exchange(0, std::memory_order_relaxed);
            snap.value_mismatch = slot.value_mismatch.exchange(0, std::memory_order_relaxed);
            snap.count_mismatch = slot.count_mismatch.exchange(0, std::memory_order_relaxed);
            snap.during_wait = slot.during_wait.exchange(0, std::memory_order_relaxed);
            snap.wait_to_signal_total_ns =
                slot.wait_to_signal_total_ns.exchange(0, std::memory_order_relaxed);
            snap.wait_to_signal_max_ns =
                slot.wait_to_signal_max_ns.exchange(0, std::memory_order_relaxed);
            snap.matched_waits = slot.matched_waits.exchange(0, std::memory_order_relaxed);
            snap.signal_to_wait_end_total_ns =
                slot.signal_to_wait_end_total_ns.exchange(0, std::memory_order_relaxed);
            snap.signal_to_wait_end_max_ns =
                slot.signal_to_wait_end_max_ns.exchange(0, std::memory_order_relaxed);

            total_calls += snap.calls;
            if (snap.calls != 0 || snap.matched_waits != 0) {
                ++active_slots;
            }
            snapshots[i] = snap;
        }

        std::sort(snapshots.begin(), snapshots.end(), [](const SignalSnapshot& lhs,
                                                         const SignalSnapshot& rhs) {
            if (lhs.matched_waits != rhs.matched_waits) {
                return lhs.matched_waits > rhs.matched_waits;
            }
            return lhs.calls > rhs.calls;
        });

        const auto& a = snapshots[0];
        const auto& b = snapshots[1];
        const auto& c = snapshots[2];
        const auto& d = snapshots[3];

        LOG_INFO(HW_GPU,
                 "[X1-ADDRSIG] frame={} frames={} addr={:#x} targetTid={:#x} slots={} sigCalls={} "
                 "waitBegin={} waitDone={} matched={} missing={} noActive={} overflow={} "
                 "top0={:#x}/{}/{}x/v{}/vvar{}/cnt{}/cvar{}/during{}/w2s{:.3f}avg/{:.3f}max/match{}/s2e{:.3f}avg/{:.3f}max "
                 "top1={:#x}/{}/{}x/v{}/vvar{}/cnt{}/cvar{}/during{}/w2s{:.3f}avg/{:.3f}max/match{}/s2e{:.3f}avg/{:.3f}max "
                 "top2={:#x}/{}/{}x/v{}/vvar{}/cnt{}/cvar{}/during{}/w2s{:.3f}avg/{:.3f}max/match{}/s2e{:.3f}avg/{:.3f}max "
                 "top3={:#x}/{}/{}x/v{}/vvar{}/cnt{}/cvar{}/during{}/w2s{:.3f}avg/{:.3f}max/match{}/s2e{:.3f}avg/{:.3f}max",
                 frame, frames, TargetSignalAddress,
                 target_wait_tid.load(std::memory_order_relaxed), active_slots, total_calls,
                 wait_begun.exchange(0, std::memory_order_relaxed),
                 wait_done.exchange(0, std::memory_order_relaxed),
                 wait_matched_signal.exchange(0, std::memory_order_relaxed),
                 wait_missing_signal.exchange(0, std::memory_order_relaxed),
                 signals_without_wait.exchange(0, std::memory_order_relaxed),
                 signal_slot_overflow.exchange(0, std::memory_order_relaxed),
                 a.thread_id, SignalTypeName(a.type), a.calls, a.value_ref, a.value_mismatch,
                 a.count_ref, a.count_mismatch, a.during_wait,
                 AvgMs(a.wait_to_signal_total_ns, a.during_wait), ToMs(a.wait_to_signal_max_ns),
                 a.matched_waits, AvgMs(a.signal_to_wait_end_total_ns, a.matched_waits),
                 ToMs(a.signal_to_wait_end_max_ns),
                 b.thread_id, SignalTypeName(b.type), b.calls, b.value_ref, b.value_mismatch,
                 b.count_ref, b.count_mismatch, b.during_wait,
                 AvgMs(b.wait_to_signal_total_ns, b.during_wait), ToMs(b.wait_to_signal_max_ns),
                 b.matched_waits, AvgMs(b.signal_to_wait_end_total_ns, b.matched_waits),
                 ToMs(b.signal_to_wait_end_max_ns),
                 c.thread_id, SignalTypeName(c.type), c.calls, c.value_ref, c.value_mismatch,
                 c.count_ref, c.count_mismatch, c.during_wait,
                 AvgMs(c.wait_to_signal_total_ns, c.during_wait), ToMs(c.wait_to_signal_max_ns),
                 c.matched_waits, AvgMs(c.signal_to_wait_end_total_ns, c.matched_waits),
                 ToMs(c.signal_to_wait_end_max_ns),
                 d.thread_id, SignalTypeName(d.type), d.calls, d.value_ref, d.value_mismatch,
                 d.count_ref, d.count_mismatch, d.during_wait,
                 AvgMs(d.wait_to_signal_total_ns, d.during_wait), ToMs(d.wait_to_signal_max_ns),
                 d.matched_waits, AvgMs(d.signal_to_wait_end_total_ns, d.matched_waits),
                 ToMs(d.signal_to_wait_end_max_ns));
    }

    static const char* TypeName(u32 type) noexcept {
        switch (type) {
        case 0:
            return "less";
        case 1:
            return "decLess";
        case 2:
            return "equal";
        default:
            return "unknown";
        }
    }

    static const char* SignalTypeName(u32 type) noexcept {
        switch (type) {
        case 0:
            return "signal";
        case 1:
            return "incEq";
        case 2:
            return "modWaitEq";
        default:
            return "unknown";
        }
    }

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

    std::atomic<bool> enabled{false};
    std::atomic<bool> armed{false};
    std::atomic<u64> target_tid{0};
    std::atomic<u64> target_switches{0};
    std::atomic<u64> slot_overflow{0};
    std::atomic<u64> frame_id{0};
    std::array<Slot, SlotCount> slots{};

    std::atomic<u64> signal_slot_overflow{0};
    std::atomic<u64> target_wait_start_ns{0};
    std::atomic<u64> target_wait_tid{0};
    std::atomic<u64> wait_begun{0};
    std::atomic<u64> wait_done{0};
    std::atomic<u64> wait_matched_signal{0};
    std::atomic<u64> wait_missing_signal{0};
    std::atomic<u64> signals_without_wait{0};
    std::atomic<u64> latest_signal_ns{0};
    std::atomic<u32> latest_signal_slot{0};
    std::array<SignalSlot, SignalSlotCount> signal_slots{};

    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace Core
