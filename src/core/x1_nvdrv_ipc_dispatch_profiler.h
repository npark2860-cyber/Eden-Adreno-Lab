// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <mutex>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1NvdrvIpcDispatchProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1NvdrvIpcDispatchProfiler& Get() {
        static X1NvdrvIpcDispatchProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_nvdrv_ipc_dispatch_gap_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (!on) {
            return;
        }

        for (auto& slot : sync_entries) {
            slot.owner_tid.store(0, std::memory_order_relaxed);
            slot.entry_ns.store(0, std::memory_order_relaxed);
        }

        std::scoped_lock lk(mutex);
        candidates = {};
        frame_id.store(0, std::memory_order_relaxed);
        frames_since_report = 0;
        report_start = Clock::now();
        sync_entries_recorded.store(0, std::memory_order_relaxed);
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void RecordSyncRequestEntry(u64 thread_id) noexcept {
        if (!Enabled() || thread_id == 0) {
            return;
        }

        const u64 now_ns = NowNs();
        auto& slot = sync_entries[thread_id % SyncSlotCount];
        slot.owner_tid.store(0, std::memory_order_release);
        slot.entry_ns.store(now_ns, std::memory_order_relaxed);
        slot.owner_tid.store(thread_id, std::memory_order_release);
        sync_entries_recorded.fetch_add(1, std::memory_order_relaxed);
    }

    void RecordNvdrvHandlerEntry(u64 thread_id, u32 ioctl_kind) noexcept {
        if (!Enabled() || thread_id == 0) {
            return;
        }

        const u64 now_ns = NowNs();
        const auto sync_entry = LoadSyncEntry(thread_id);

        std::scoped_lock lk(mutex);
        CandidateSlot* slot = FindOrAllocate(thread_id);
        if (slot == nullptr) {
            ++overflow_requests;
            return;
        }

        ++slot->requests;
        if (ioctl_kind == 1) {
            ++slot->ioctl1;
        } else if (ioctl_kind == 2) {
            ++slot->ioctl2;
        }

        if (sync_entry != 0 && now_ns >= sync_entry) {
            const u64 dispatch_ns = now_ns - sync_entry;
            ++slot->dispatch_count;
            slot->dispatch_ns += dispatch_ns;
            slot->dispatch_max_ns = std::max(slot->dispatch_max_ns, dispatch_ns);

            if (slot->last_complete_ns != 0 && sync_entry >= slot->last_complete_ns) {
                const u64 guest_post_ns = sync_entry - slot->last_complete_ns;
                ++slot->guest_post_count;
                slot->guest_post_ns += guest_post_ns;
                slot->guest_post_max_ns = std::max(slot->guest_post_max_ns, guest_post_ns);
            }
        } else {
            ++slot->missing_sync_entry;
        }

        slot->active_handler_start_ns = now_ns;
    }

    void RecordNvdrvHandlerComplete(u64 thread_id) noexcept {
        if (!Enabled() || thread_id == 0) {
            return;
        }

        const u64 now_ns = NowNs();
        std::scoped_lock lk(mutex);
        CandidateSlot* slot = FindExisting(thread_id);
        if (slot == nullptr) {
            ++orphan_completions;
            return;
        }

        if (slot->active_handler_start_ns != 0 && now_ns >= slot->active_handler_start_ns) {
            const u64 service_ns = now_ns - slot->active_handler_start_ns;
            ++slot->service_count;
            slot->service_ns += service_ns;
            slot->service_max_ns = std::max(slot->service_max_ns, service_ns);
        } else {
            ++slot->missing_handler_start;
        }

        slot->last_complete_ns = now_ns;
        slot->active_handler_start_ns = 0;
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
        u64 total_requests{};
        u64 active_threads{};
        u64 overflow{};
        u64 orphan{};
        {
            std::scoped_lock lk(mutex);
            overflow = overflow_requests;
            orphan = orphan_completions;
            overflow_requests = 0;
            orphan_completions = 0;

            for (auto& slot : candidates) {
                if (slot.thread_id == 0 || slot.requests == 0) {
                    continue;
                }
                ++active_threads;
                total_requests += slot.requests;
                if (slot.requests > dominant.requests) {
                    dominant = Snapshot::From(slot);
                }
                slot.ResetWindow();
            }
        }

        const double dominant_share =
            total_requests == 0 ? 0.0
                                : 100.0 * static_cast<double>(dominant.requests) /
                                      static_cast<double>(total_requests);

        LOG_INFO(HW_GPU,
                 "[X1-IPCDISPATCH] frame={} frames={} wall={:.3f}ms threads={} requests={} "
                 "syncEntries={} overflow={} orphan={} tid={:#x} domReq={} domShare={:.2f}% "
                 "ioctl1={} ioctl2={} guestPostN={} guestPost={:.3f}ms guestPostAvg={:.3f}ms "
                 "guestPostMax={:.3f}ms dispatchN={} ipcDispatch={:.3f}ms ipcDispatchAvg={:.3f}ms "
                 "ipcDispatchMax={:.3f}ms serviceN={} serviceReply={:.3f}ms serviceReplyAvg={:.3f}ms "
                 "serviceReplyMax={:.3f}ms missingA={} missingB={}",
                 frame, frames, ToMs(wall_ns), active_threads, total_requests,
                 sync_entries_recorded.exchange(0, std::memory_order_relaxed), overflow, orphan,
                 dominant.thread_id, dominant.requests, dominant_share, dominant.ioctl1,
                 dominant.ioctl2, dominant.guest_post_count, ToMs(dominant.guest_post_ns),
                 AvgMs(dominant.guest_post_ns, dominant.guest_post_count),
                 ToMs(dominant.guest_post_max_ns), dominant.dispatch_count,
                 ToMs(dominant.dispatch_ns), AvgMs(dominant.dispatch_ns, dominant.dispatch_count),
                 ToMs(dominant.dispatch_max_ns), dominant.service_count,
                 ToMs(dominant.service_ns), AvgMs(dominant.service_ns, dominant.service_count),
                 ToMs(dominant.service_max_ns), dominant.missing_sync_entry,
                 dominant.missing_handler_start);
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t SyncSlotCount = 256;
    static constexpr size_t MaxCandidateThreads = 8;

    struct SyncEntrySlot {
        std::atomic<u64> owner_tid{0};
        std::atomic<u64> entry_ns{0};
    };

    struct CandidateSlot {
        u64 thread_id{};
        u64 last_complete_ns{};
        u64 active_handler_start_ns{};
        u64 requests{};
        u64 ioctl1{};
        u64 ioctl2{};
        u64 guest_post_count{};
        u64 guest_post_ns{};
        u64 guest_post_max_ns{};
        u64 dispatch_count{};
        u64 dispatch_ns{};
        u64 dispatch_max_ns{};
        u64 service_count{};
        u64 service_ns{};
        u64 service_max_ns{};
        u64 missing_sync_entry{};
        u64 missing_handler_start{};

        void ResetWindow() noexcept {
            requests = 0;
            ioctl1 = 0;
            ioctl2 = 0;
            guest_post_count = 0;
            guest_post_ns = 0;
            guest_post_max_ns = 0;
            dispatch_count = 0;
            dispatch_ns = 0;
            dispatch_max_ns = 0;
            service_count = 0;
            service_ns = 0;
            service_max_ns = 0;
            missing_sync_entry = 0;
            missing_handler_start = 0;
        }
    };

    struct Snapshot {
        u64 thread_id{};
        u64 requests{};
        u64 ioctl1{};
        u64 ioctl2{};
        u64 guest_post_count{};
        u64 guest_post_ns{};
        u64 guest_post_max_ns{};
        u64 dispatch_count{};
        u64 dispatch_ns{};
        u64 dispatch_max_ns{};
        u64 service_count{};
        u64 service_ns{};
        u64 service_max_ns{};
        u64 missing_sync_entry{};
        u64 missing_handler_start{};

        static Snapshot From(const CandidateSlot& slot) noexcept {
            Snapshot out{};
            out.thread_id = slot.thread_id;
            out.requests = slot.requests;
            out.ioctl1 = slot.ioctl1;
            out.ioctl2 = slot.ioctl2;
            out.guest_post_count = slot.guest_post_count;
            out.guest_post_ns = slot.guest_post_ns;
            out.guest_post_max_ns = slot.guest_post_max_ns;
            out.dispatch_count = slot.dispatch_count;
            out.dispatch_ns = slot.dispatch_ns;
            out.dispatch_max_ns = slot.dispatch_max_ns;
            out.service_count = slot.service_count;
            out.service_ns = slot.service_ns;
            out.service_max_ns = slot.service_max_ns;
            out.missing_sync_entry = slot.missing_sync_entry;
            out.missing_handler_start = slot.missing_handler_start;
            return out;
        }
    };

    [[nodiscard]] u64 LoadSyncEntry(u64 thread_id) const noexcept {
        const auto& slot = sync_entries[thread_id % SyncSlotCount];
        const u64 owner_before = slot.owner_tid.load(std::memory_order_acquire);
        const u64 entry = slot.entry_ns.load(std::memory_order_relaxed);
        const u64 owner_after = slot.owner_tid.load(std::memory_order_acquire);
        if (owner_before == thread_id && owner_after == thread_id) {
            return entry;
        }
        return 0;
    }

    CandidateSlot* FindExisting(u64 thread_id) noexcept {
        for (auto& slot : candidates) {
            if (slot.thread_id == thread_id) {
                return &slot;
            }
        }
        return nullptr;
    }

    CandidateSlot* FindOrAllocate(u64 thread_id) noexcept {
        if (auto* slot = FindExisting(thread_id); slot != nullptr) {
            return slot;
        }
        for (auto& slot : candidates) {
            if (slot.thread_id == 0) {
                slot.thread_id = thread_id;
                return &slot;
            }
        }
        return nullptr;
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

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    std::atomic<u64> sync_entries_recorded{0};
    std::array<SyncEntrySlot, SyncSlotCount> sync_entries{};
    std::mutex mutex;
    std::array<CandidateSlot, MaxCandidateThreads> candidates{};
    u64 overflow_requests{};
    u64 orphan_completions{};
    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace Core
