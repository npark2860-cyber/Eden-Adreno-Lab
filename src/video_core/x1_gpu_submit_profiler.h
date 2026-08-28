// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>
#include <chrono>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace VideoCore {

class X1GpuSubmitProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1GpuSubmitProfiler& Get() {
        static X1GpuSubmitProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_gpu_submit_gap_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (on) {
            report_start = Clock::now();
            last_service_entry_ns.store(0, std::memory_order_relaxed);
            last_device_entry_ns.store(0, std::memory_order_relaxed);
            last_submit_push_ns.store(0, std::memory_order_relaxed);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    static TimePoint Now() noexcept { return Clock::now(); }

    static u64 ElapsedNs(TimePoint start) noexcept {
        return static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count());
    }

    static u64 NowNs() noexcept {
        return static_cast<u64>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                    Clock::now().time_since_epoch())
                                    .count());
    }

    void RecordServiceEntry(u32 kind) noexcept {
        if (!Enabled()) return;
        Add(counters.service_entries, 1);
        if (kind == 1) Add(counters.service_ioctl1, 1);
        if (kind == 2) Add(counters.service_ioctl2, 1);
        RecordGap(last_service_entry_ns, counters.service_gap_count, counters.service_gap_ns,
                  counters.service_gap_max_ns);
    }

    void RecordServiceCall(u64 total_ns, u64 read_ns, u64 dispatch_ns, u64 write_ns) noexcept {
        if (!Enabled()) return;
        Add(counters.service_total_ns, total_ns);
        Add(counters.service_read_ns, read_ns);
        Add(counters.service_dispatch_ns, dispatch_ns);
        Add(counters.service_write_ns, write_ns);
    }

    void RecordDeviceEntry(u32 kind) noexcept {
        if (!Enabled()) return;
        Add(counters.device_entries, 1);
        if (kind == 1) Add(counters.device_ioctl1, 1);
        if (kind == 2) Add(counters.device_ioctl2, 1);
        RecordGap(last_device_entry_ns, counters.device_gap_count, counters.device_gap_ns,
                  counters.device_gap_max_ns);
    }

    void RecordBase(u64 total_ns, u64 alloc_ns, u64 copy_ns, u64 entries, u32 kind) noexcept {
        if (!Enabled()) return;
        Add(counters.base_calls, 1);
        Add(counters.base_total_ns, total_ns);
        Add(counters.base_alloc_ns, alloc_ns);
        Add(counters.base_copy_ns, copy_ns);
        Add(counters.base_entries, entries);
        if (kind == 1) Add(counters.base1_calls, 1);
        if (kind == 2) Add(counters.base2_calls, 1);
    }

    void RecordSubmitPushEntry(u32 kind) noexcept {
        if (!Enabled()) return;
        Add(counters.submit_push_entries, 1);
        if (kind == 0) Add(counters.submit_push_wait, 1);
        if (kind == 1) Add(counters.submit_push_main, 1);
        if (kind == 2) Add(counters.submit_push_fence, 1);
        RecordGap(last_submit_push_ns, counters.submit_push_gap_count, counters.submit_push_gap_ns,
                  counters.submit_push_gap_max_ns);
    }

    void RecordImpl(u64 total_ns, u64 lock_wait_ns, u64 init_ns, u64 fence_check_ns,
                    u64 syncpoint_ns, u64 wait_push_ns, u64 main_push_ns,
                    u64 fence_push_ns) noexcept {
        if (!Enabled()) return;
        Add(counters.impl_calls, 1);
        Add(counters.impl_total_ns, total_ns);
        Add(counters.impl_lock_wait_ns, lock_wait_ns);
        Add(counters.impl_init_ns, init_ns);
        Add(counters.impl_fence_check_ns, fence_check_ns);
        Add(counters.impl_syncpoint_ns, syncpoint_ns);
        Add(counters.impl_wait_push_ns, wait_push_ns);
        Add(counters.impl_main_push_ns, main_push_ns);
        Add(counters.impl_fence_push_ns, fence_push_ns);
    }

    void FrameEnd() {
        if (!Enabled()) return;
        const u64 frame = frame_id.fetch_add(1, std::memory_order_relaxed) + 1;
        ++frames_since_report;
        if (frames_since_report < ReportFrames) return;

        const auto now = Clock::now();
        const u64 wall_ns = report_start == TimePoint{} ? 0 : static_cast<u64>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(now - report_start).count());
        report_start = now;
        const u64 frames = frames_since_report;
        frames_since_report = 0;

        const u64 service_entries = Take(counters.service_entries);
        const u64 service_ioctl1 = Take(counters.service_ioctl1);
        const u64 service_ioctl2 = Take(counters.service_ioctl2);
        const u64 service_gap_count = Take(counters.service_gap_count);
        const u64 service_gap_ns = Take(counters.service_gap_ns);
        const u64 service_gap_max_ns = Take(counters.service_gap_max_ns);
        const u64 service_total_ns = Take(counters.service_total_ns);
        const u64 service_read_ns = Take(counters.service_read_ns);
        const u64 service_dispatch_ns = Take(counters.service_dispatch_ns);
        const u64 service_write_ns = Take(counters.service_write_ns);

        const u64 device_entries = Take(counters.device_entries);
        const u64 device_ioctl1 = Take(counters.device_ioctl1);
        const u64 device_ioctl2 = Take(counters.device_ioctl2);
        const u64 device_gap_count = Take(counters.device_gap_count);
        const u64 device_gap_ns = Take(counters.device_gap_ns);
        const u64 device_gap_max_ns = Take(counters.device_gap_max_ns);

        const u64 base_calls = Take(counters.base_calls);
        const u64 base1_calls = Take(counters.base1_calls);
        const u64 base2_calls = Take(counters.base2_calls);
        const u64 base_total_ns = Take(counters.base_total_ns);
        const u64 base_alloc_ns = Take(counters.base_alloc_ns);
        const u64 base_copy_ns = Take(counters.base_copy_ns);
        const u64 base_entries = Take(counters.base_entries);

        const u64 submit_push_entries = Take(counters.submit_push_entries);
        const u64 submit_push_wait = Take(counters.submit_push_wait);
        const u64 submit_push_main = Take(counters.submit_push_main);
        const u64 submit_push_fence = Take(counters.submit_push_fence);
        const u64 submit_push_gap_count = Take(counters.submit_push_gap_count);
        const u64 submit_push_gap_ns = Take(counters.submit_push_gap_ns);
        const u64 submit_push_gap_max_ns = Take(counters.submit_push_gap_max_ns);

        const u64 impl_calls = Take(counters.impl_calls);
        const u64 impl_total_ns = Take(counters.impl_total_ns);
        const u64 impl_lock_wait_ns = Take(counters.impl_lock_wait_ns);
        const u64 impl_init_ns = Take(counters.impl_init_ns);
        const u64 impl_fence_check_ns = Take(counters.impl_fence_check_ns);
        const u64 impl_syncpoint_ns = Take(counters.impl_syncpoint_ns);
        const u64 impl_wait_push_ns = Take(counters.impl_wait_push_ns);
        const u64 impl_main_push_ns = Take(counters.impl_main_push_ns);
        const u64 impl_fence_push_ns = Take(counters.impl_fence_push_ns);

        LOG_INFO(HW_GPU,
                 "[X1-GPUSUBMIT] frame={} frames={} wall={:.3f}ms "
                 "service={} ioctl1={} ioctl2={} serviceGapN={} serviceGap={:.3f}ms serviceGapMax={:.3f}ms "
                 "serviceTime={:.3f}ms read={:.3f}ms dispatch={:.3f}ms write={:.3f}ms "
                 "device={} dev1={} dev2={} deviceGapN={} deviceGap={:.3f}ms deviceGapMax={:.3f}ms "
                 "base={} base1={} base2={} baseTime={:.3f}ms alloc={:.3f}ms copy={:.3f}ms entries={} "
                 "pushEntries={} waitPush={} mainPush={} fencePush={} pushGapN={} pushGap={:.3f}ms pushGapMax={:.3f}ms "
                 "impl={} implTime={:.3f}ms lockWait={:.3f}ms init={:.3f}ms fenceCheck={:.3f}ms syncpoint={:.3f}ms "
                 "waitPushTime={:.3f}ms mainPushTime={:.3f}ms fencePushTime={:.3f}ms",
                 frame, frames, ToMs(wall_ns), service_entries, service_ioctl1, service_ioctl2,
                 service_gap_count, ToMs(service_gap_ns), ToMs(service_gap_max_ns),
                 ToMs(service_total_ns), ToMs(service_read_ns), ToMs(service_dispatch_ns),
                 ToMs(service_write_ns), device_entries, device_ioctl1, device_ioctl2,
                 device_gap_count, ToMs(device_gap_ns), ToMs(device_gap_max_ns), base_calls,
                 base1_calls, base2_calls, ToMs(base_total_ns), ToMs(base_alloc_ns),
                 ToMs(base_copy_ns), base_entries, submit_push_entries, submit_push_wait,
                 submit_push_main, submit_push_fence, submit_push_gap_count, ToMs(submit_push_gap_ns),
                 ToMs(submit_push_gap_max_ns), impl_calls, ToMs(impl_total_ns),
                 ToMs(impl_lock_wait_ns), ToMs(impl_init_ns), ToMs(impl_fence_check_ns),
                 ToMs(impl_syncpoint_ns), ToMs(impl_wait_push_ns), ToMs(impl_main_push_ns),
                 ToMs(impl_fence_push_ns));
    }

private:
    static constexpr u64 ReportFrames = 120;

    static void Add(std::atomic<u64>& dst, u64 value) noexcept {
        dst.fetch_add(value, std::memory_order_relaxed);
    }

    static u64 Take(std::atomic<u64>& value) noexcept {
        return value.exchange(0, std::memory_order_relaxed);
    }

    static double ToMs(u64 ns) noexcept {
        return static_cast<double>(ns) / 1'000'000.0;
    }

    static void UpdateMax(std::atomic<u64>& dst, u64 value) noexcept {
        u64 current = dst.load(std::memory_order_relaxed);
        while (current < value &&
               !dst.compare_exchange_weak(current, value, std::memory_order_relaxed,
                                          std::memory_order_relaxed)) {
        }
    }

    static void RecordGap(std::atomic<u64>& last, std::atomic<u64>& count,
                          std::atomic<u64>& sum, std::atomic<u64>& max) noexcept {
        const u64 now = NowNs();
        const u64 previous = last.exchange(now, std::memory_order_relaxed);
        if (previous == 0 || now < previous) return;
        const u64 gap = now - previous;
        Add(count, 1);
        Add(sum, gap);
        UpdateMax(max, gap);
    }

    struct Counters {
        std::atomic<u64> service_entries{0}, service_ioctl1{0}, service_ioctl2{0};
        std::atomic<u64> service_gap_count{0}, service_gap_ns{0}, service_gap_max_ns{0};
        std::atomic<u64> service_total_ns{0}, service_read_ns{0}, service_dispatch_ns{0}, service_write_ns{0};

        std::atomic<u64> device_entries{0}, device_ioctl1{0}, device_ioctl2{0};
        std::atomic<u64> device_gap_count{0}, device_gap_ns{0}, device_gap_max_ns{0};

        std::atomic<u64> base_calls{0}, base1_calls{0}, base2_calls{0};
        std::atomic<u64> base_total_ns{0}, base_alloc_ns{0}, base_copy_ns{0}, base_entries{0};

        std::atomic<u64> submit_push_entries{0}, submit_push_wait{0}, submit_push_main{0}, submit_push_fence{0};
        std::atomic<u64> submit_push_gap_count{0}, submit_push_gap_ns{0}, submit_push_gap_max_ns{0};

        std::atomic<u64> impl_calls{0}, impl_total_ns{0}, impl_lock_wait_ns{0}, impl_init_ns{0};
        std::atomic<u64> impl_fence_check_ns{0}, impl_syncpoint_ns{0};
        std::atomic<u64> impl_wait_push_ns{0}, impl_main_push_ns{0}, impl_fence_push_ns{0};
    } counters;

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    std::atomic<u64> last_service_entry_ns{0};
    std::atomic<u64> last_device_entry_ns{0};
    std::atomic<u64> last_submit_push_ns{0};
    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace VideoCore
