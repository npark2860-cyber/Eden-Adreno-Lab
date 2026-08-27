// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>
#include <chrono>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace VideoCore {

class X1GpuCommandProfiler final {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    static X1GpuCommandProfiler& Get() {
        static X1GpuCommandProfiler profiler;
        return profiler;
    }

    void Initialize(bool is_qualcomm_proprietary) noexcept {
        const bool on = is_qualcomm_proprietary &&
                        Settings::values.x1_gpu_command_attribution_log.GetValue();
        enabled.store(on, std::memory_order_relaxed);
        if (on) {
            report_start = Clock::now();
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

    void RecordWorkerQueueWait(u64 ns) noexcept {
        if (Enabled()) {
            Add(counters.worker_pop_calls, 1);
            Add(counters.worker_queue_wait_ns, ns);
        }
    }

    void RecordWorkerCommand(u64 total_ns, u32 kind) noexcept {
        if (!Enabled()) return;
        Add(counters.worker_active_ns, total_ns);
        switch (kind) {
        case 0: Add(counters.worker_submit_calls, 1); Add(counters.worker_submit_ns, total_ns); break;
        case 1: Add(counters.worker_tick_calls, 1); Add(counters.worker_tick_ns, total_ns); break;
        case 2: Add(counters.worker_flush_calls, 1); Add(counters.worker_flush_ns, total_ns); break;
        case 3: Add(counters.worker_invalidate_calls, 1); Add(counters.worker_invalidate_ns, total_ns); break;
        default: Add(counters.worker_other_calls, 1); Add(counters.worker_other_ns, total_ns); break;
        }
    }

    void RecordPushCommand(u64 total_ns, u64 block_wait_ns, bool blocked) noexcept {
        if (!Enabled()) return;
        Add(counters.push_command_calls, 1);
        Add(counters.push_command_ns, total_ns);
        if (blocked) {
            Add(counters.push_block_calls, 1);
            Add(counters.push_block_wait_ns, block_wait_ns);
        }
    }

    void RecordSchedulerPush(u64 total_ns, u64 bind_ns, u64 dispatch_ns) noexcept {
        if (!Enabled()) return;
        Add(counters.scheduler_calls, 1);
        Add(counters.scheduler_total_ns, total_ns);
        Add(counters.scheduler_bind_ns, bind_ns);
        Add(counters.scheduler_dispatch_ns, dispatch_ns);
    }

    void RecordDmaDispatch(u64 total_ns, u64 loop_ns, u64 tail_ns, u64 step_calls) noexcept {
        if (!Enabled()) return;
        Add(counters.dma_dispatch_calls, 1);
        Add(counters.dma_dispatch_total_ns, total_ns);
        Add(counters.dma_loop_ns, loop_ns);
        Add(counters.dma_tail_ns, tail_ns);
        Add(counters.dma_step_calls, step_calls);
    }

    void RecordDmaSyncWait(u64 ns) noexcept {
        if (Enabled()) {
            Add(counters.dma_sync_wait_calls, 1);
            Add(counters.dma_sync_wait_ns, ns);
        }
    }

    void RecordProcessCommands(u64 total_ns, u64 words) noexcept {
        if (!Enabled()) return;
        Add(counters.process_calls, 1);
        Add(counters.process_ns, total_ns);
        Add(counters.process_words, words);
    }

    void CountCallMethod() noexcept {
        if (Enabled()) Add(counters.call_method_calls, 1);
    }

    void CountCallMultiMethod(u64 methods) noexcept {
        if (Enabled()) {
            Add(counters.call_multi_calls, 1);
            Add(counters.call_multi_methods, methods);
        }
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

        const u64 worker_pop_calls = Take(counters.worker_pop_calls);
        const u64 worker_queue_wait_ns = Take(counters.worker_queue_wait_ns);
        const u64 worker_active_ns = Take(counters.worker_active_ns);
        const u64 worker_submit_calls = Take(counters.worker_submit_calls);
        const u64 worker_submit_ns = Take(counters.worker_submit_ns);
        const u64 worker_tick_calls = Take(counters.worker_tick_calls);
        const u64 worker_tick_ns = Take(counters.worker_tick_ns);
        const u64 worker_flush_calls = Take(counters.worker_flush_calls);
        const u64 worker_flush_ns = Take(counters.worker_flush_ns);
        const u64 worker_invalidate_calls = Take(counters.worker_invalidate_calls);
        const u64 worker_invalidate_ns = Take(counters.worker_invalidate_ns);
        const u64 worker_other_calls = Take(counters.worker_other_calls);
        const u64 worker_other_ns = Take(counters.worker_other_ns);
        const u64 push_command_calls = Take(counters.push_command_calls);
        const u64 push_command_ns = Take(counters.push_command_ns);
        const u64 push_block_calls = Take(counters.push_block_calls);
        const u64 push_block_wait_ns = Take(counters.push_block_wait_ns);
        const u64 scheduler_calls = Take(counters.scheduler_calls);
        const u64 scheduler_total_ns = Take(counters.scheduler_total_ns);
        const u64 scheduler_bind_ns = Take(counters.scheduler_bind_ns);
        const u64 scheduler_dispatch_ns = Take(counters.scheduler_dispatch_ns);
        const u64 dma_dispatch_calls = Take(counters.dma_dispatch_calls);
        const u64 dma_dispatch_total_ns = Take(counters.dma_dispatch_total_ns);
        const u64 dma_loop_ns = Take(counters.dma_loop_ns);
        const u64 dma_tail_ns = Take(counters.dma_tail_ns);
        const u64 dma_step_calls = Take(counters.dma_step_calls);
        const u64 dma_sync_wait_calls = Take(counters.dma_sync_wait_calls);
        const u64 dma_sync_wait_ns = Take(counters.dma_sync_wait_ns);
        const u64 process_calls = Take(counters.process_calls);
        const u64 process_ns = Take(counters.process_ns);
        const u64 process_words = Take(counters.process_words);
        const u64 call_method_calls = Take(counters.call_method_calls);
        const u64 call_multi_calls = Take(counters.call_multi_calls);
        const u64 call_multi_methods = Take(counters.call_multi_methods);

        LOG_INFO(HW_GPU,
                 "[X1-GPUCMD] frame={} frames={} wall={:.3f}ms "
                 "workerPop={} queueWait={:.3f}ms active={:.3f}ms "
                 "submitCalls={} submit={:.3f}ms tickCalls={} tick={:.3f}ms "
                 "flushCalls={} flush={:.3f}ms invalCalls={} inval={:.3f}ms otherCalls={} other={:.3f}ms "
                 "pushCalls={} push={:.3f}ms blockCalls={} blockWait={:.3f}ms "
                 "schedCalls={} sched={:.3f}ms bind={:.3f}ms dispatch={:.3f}ms "
                 "dmaCalls={} dma={:.3f}ms loop={:.3f}ms tail={:.3f}ms steps={} "
                 "syncWaitCalls={} syncWait={:.3f}ms processCalls={} process={:.3f}ms words={} "
                 "callMethod={} callMulti={} multiMethods={}",
                 frame, frames, ToMs(wall_ns), worker_pop_calls, ToMs(worker_queue_wait_ns),
                 ToMs(worker_active_ns), worker_submit_calls, ToMs(worker_submit_ns),
                 worker_tick_calls, ToMs(worker_tick_ns), worker_flush_calls, ToMs(worker_flush_ns),
                 worker_invalidate_calls, ToMs(worker_invalidate_ns), worker_other_calls,
                 ToMs(worker_other_ns), push_command_calls, ToMs(push_command_ns), push_block_calls,
                 ToMs(push_block_wait_ns), scheduler_calls, ToMs(scheduler_total_ns),
                 ToMs(scheduler_bind_ns), ToMs(scheduler_dispatch_ns), dma_dispatch_calls,
                 ToMs(dma_dispatch_total_ns), ToMs(dma_loop_ns), ToMs(dma_tail_ns), dma_step_calls,
                 dma_sync_wait_calls, ToMs(dma_sync_wait_ns), process_calls, ToMs(process_ns),
                 process_words, call_method_calls, call_multi_calls, call_multi_methods);
    }

private:
    static constexpr u64 ReportFrames = 120;
    static void Add(std::atomic<u64>& dst, u64 value) noexcept { dst.fetch_add(value, std::memory_order_relaxed); }
    static u64 Take(std::atomic<u64>& value) noexcept { return value.exchange(0, std::memory_order_relaxed); }
    static double ToMs(u64 ns) noexcept { return static_cast<double>(ns) / 1'000'000.0; }

    struct Counters {
        std::atomic<u64> worker_pop_calls{0}, worker_queue_wait_ns{0}, worker_active_ns{0};
        std::atomic<u64> worker_submit_calls{0}, worker_submit_ns{0}, worker_tick_calls{0}, worker_tick_ns{0};
        std::atomic<u64> worker_flush_calls{0}, worker_flush_ns{0}, worker_invalidate_calls{0}, worker_invalidate_ns{0};
        std::atomic<u64> worker_other_calls{0}, worker_other_ns{0};
        std::atomic<u64> push_command_calls{0}, push_command_ns{0}, push_block_calls{0}, push_block_wait_ns{0};
        std::atomic<u64> scheduler_calls{0}, scheduler_total_ns{0}, scheduler_bind_ns{0}, scheduler_dispatch_ns{0};
        std::atomic<u64> dma_dispatch_calls{0}, dma_dispatch_total_ns{0}, dma_loop_ns{0}, dma_tail_ns{0}, dma_step_calls{0};
        std::atomic<u64> dma_sync_wait_calls{0}, dma_sync_wait_ns{0}, process_calls{0}, process_ns{0}, process_words{0};
        std::atomic<u64> call_method_calls{0}, call_multi_calls{0}, call_multi_methods{0};
    } counters;

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    TimePoint report_start{};
};

} // namespace VideoCore
