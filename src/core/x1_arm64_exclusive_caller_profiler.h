// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <limits>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1Arm64ExclusiveCallerProfiler final {
public:
    static constexpr u32 SampleRate = 64;
    static constexpr u64 EnterLdaxrOffset = 0x131754;
    static constexpr u64 LockMutexCallerLrStackOffset = 0x38;
    static_assert((SampleRate & (SampleRate - 1)) == 0);

    static X1Arm64ExclusiveCallerProfiler& Get() {
        static X1Arm64ExclusiveCallerProfiler profiler;
        return profiler;
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
        for (size_t producer_index = 0; producer_index < ProducerCount; ++producer_index) {
            auto& producer = producers[producer_index];
            producer.invalid_stack_samples.store(0, std::memory_order_relaxed);
            producer.dropped_samples.store(0, std::memory_order_relaxed);
            previous_invalid[producer_index] = 0;
            previous_dropped[producer_index] = 0;
            for (size_t slot_index = 0; slot_index < CallerSlotCount; ++slot_index) {
                auto& slot = producer.slots[slot_index];
                slot.caller_lr.store(0, std::memory_order_relaxed);
                slot.samples.store(0, std::memory_order_relaxed);
                previous_samples[producer_index][slot_index] = 0;
            }
        }
    }

    void RegisterSdkModuleRange(u64 start, u64 end) noexcept {
        if (start == 0 || end <= start || end - start <= EnterLdaxrOffset) {
            return;
        }
        sdk_start.store(start, std::memory_order_relaxed);
        sdk_end.store(end, std::memory_order_relaxed);
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    [[nodiscard]] bool IsTargetEnterPc(u64 guest_pc) const noexcept {
        const u64 start = sdk_start.load(std::memory_order_relaxed);
        const u64 end = sdk_end.load(std::memory_order_relaxed);
        if (start == 0 || end <= start || start > std::numeric_limits<u64>::max() - EnterLdaxrOffset) {
            return false;
        }
        const u64 target = start + EnterLdaxrOffset;
        return target < end && guest_pc == target;
    }

    void RecordInvalidStack(u32 producer_index) noexcept {
        if (!Enabled() || producer_index >= ProducerCount) {
            return;
        }
        producers[producer_index].invalid_stack_samples.fetch_add(1, std::memory_order_relaxed);
    }

    void RecordCallerSample(u32 producer_index, u64 caller_lr) noexcept {
        if (!Enabled() || producer_index >= ProducerCount || caller_lr == 0) {
            return;
        }

        auto& producer = producers[producer_index];
        size_t slot_index = CallerHash(caller_lr);
        for (size_t probe = 0; probe < CallerProbeCount; ++probe) {
            auto& slot = producer.slots[slot_index];
            u64 key = slot.caller_lr.load(std::memory_order_relaxed);
            if (key == caller_lr) {
                slot.samples.fetch_add(1, std::memory_order_relaxed);
                return;
            }
            if (key == 0) {
                u64 expected = 0;
                if (slot.caller_lr.compare_exchange_strong(expected, caller_lr,
                                                           std::memory_order_relaxed,
                                                           std::memory_order_relaxed) ||
                    expected == caller_lr) {
                    slot.samples.fetch_add(1, std::memory_order_relaxed);
                    return;
                }
            }
            slot_index = (slot_index + 1) & (CallerSlotCount - 1);
        }
        producer.dropped_samples.fetch_add(1, std::memory_order_relaxed);
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
            ReportProducer(frame, frames, producer_index);
        }
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ProducerCount = 2;
    static constexpr size_t CallerSlotCount = 256;
    static constexpr size_t CallerProbeCount = 8;
    static constexpr size_t CallerReportTopCount = 12;
    static_assert((CallerSlotCount & (CallerSlotCount - 1)) == 0);

    struct CallerSlot {
        std::atomic<u64> caller_lr{0};
        std::atomic<u64> samples{0};
    };

    struct ProducerState {
        std::array<CallerSlot, CallerSlotCount> slots{};
        std::atomic<u64> invalid_stack_samples{0};
        std::atomic<u64> dropped_samples{0};
    };

    struct CallerDelta {
        u64 caller_lr{};
        u64 samples{};
    };

    static size_t CallerHash(u64 caller_lr) noexcept {
        constexpr u64 Golden = 0x9e3779b97f4a7c15ULL;
        return static_cast<size_t>(((caller_lr >> 2) * Golden) & (CallerSlotCount - 1));
    }

    void ReportProducer(u64 frame, u64 frames, size_t producer_index) noexcept {
        auto& producer = producers[producer_index];
        std::array<CallerDelta, CallerSlotCount> deltas{};
        size_t delta_count = 0;
        size_t occupied = 0;
        u64 total_samples = 0;

        for (size_t slot_index = 0; slot_index < CallerSlotCount; ++slot_index) {
            const auto& slot = producer.slots[slot_index];
            const u64 caller_lr = slot.caller_lr.load(std::memory_order_relaxed);
            if (caller_lr != 0) {
                ++occupied;
            }
            const u64 samples = slot.samples.load(std::memory_order_relaxed);
            const u64 previous = previous_samples[producer_index][slot_index];
            previous_samples[producer_index][slot_index] = samples;
            const u64 delta = samples - previous;
            if (caller_lr == 0 || delta == 0) {
                continue;
            }
            deltas[delta_count++] = CallerDelta{caller_lr, delta};
            total_samples += delta;
        }

        std::sort(deltas.begin(), deltas.begin() + static_cast<std::ptrdiff_t>(delta_count),
                  [](const CallerDelta& lhs, const CallerDelta& rhs) {
                      return lhs.samples > rhs.samples;
                  });

        const size_t top_count = std::min(delta_count, CallerReportTopCount);
        u64 top_samples = 0;
        for (size_t i = 0; i < top_count; ++i) {
            top_samples += deltas[i].samples;
        }

        const u64 invalid_now =
            producer.invalid_stack_samples.load(std::memory_order_relaxed);
        const u64 invalid_delta = invalid_now - previous_invalid[producer_index];
        previous_invalid[producer_index] = invalid_now;
        const u64 dropped_now = producer.dropped_samples.load(std::memory_order_relaxed);
        const u64 dropped_delta = dropped_now - previous_dropped[producer_index];
        previous_dropped[producer_index] = dropped_now;
        const u64 coverage_permille = total_samples == 0 ? 0 : top_samples * 1000 / total_samples;

        LOG_INFO(HW_GPU,
                 "[X1-XEXCLCALL] frame={} frames={} producer={} summary sampleRate={} "
                 "samples={} topSamples={} coveragePermille={} invalidStack={} dropped={} occupied={}",
                 frame, frames, producer_index, SampleRate, total_samples, top_samples,
                 coverage_permille, invalid_delta, dropped_delta, occupied);

        for (size_t rank = 0; rank < top_count; ++rank) {
            const auto& entry = deltas[rank];
            LOG_INFO(HW_GPU,
                     "[X1-XEXCLCALL] frame={} frames={} producer={} rank={} caller={:#x} samples={}",
                     frame, frames, producer_index, rank, entry.caller_lr, entry.samples);
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> sdk_start{0};
    std::atomic<u64> sdk_end{0};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    std::array<ProducerState, ProducerCount> producers{};
    std::array<std::array<u64, CallerSlotCount>, ProducerCount> previous_samples{};
    std::array<u64, ProducerCount> previous_invalid{};
    std::array<u64, ProducerCount> previous_dropped{};
};

} // namespace Core
