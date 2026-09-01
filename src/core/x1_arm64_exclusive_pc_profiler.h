// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1Arm64ExclusivePcProfiler final {
public:
    static constexpr u32 SampleRate = 16;
    static_assert((SampleRate & (SampleRate - 1)) == 0);

    static X1Arm64ExclusivePcProfiler& Get() {
        static X1Arm64ExclusivePcProfiler profiler;
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
            producer.dropped_samples.store(0, std::memory_order_relaxed);
            previous_dropped[producer_index] = 0;
            for (size_t slot_index = 0; slot_index < PcSlotCount; ++slot_index) {
                auto& slot = producer.slots[slot_index];
                slot.pc.store(0, std::memory_order_relaxed);
                slot.samples.store(0, std::memory_order_relaxed);
                slot.sample_ns.store(0, std::memory_order_relaxed);
                previous_samples[producer_index][slot_index] = 0;
                previous_ns[producer_index][slot_index] = 0;
            }
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void RecordReadSample(u32 producer_index, u64 guest_pc, u64 elapsed_ns) noexcept {
        if (!Enabled() || producer_index >= ProducerCount || guest_pc == 0) {
            return;
        }

        auto& producer = producers[producer_index];
        size_t slot_index = PcHash(guest_pc);
        for (size_t probe = 0; probe < PcProbeCount; ++probe) {
            auto& slot = producer.slots[slot_index];
            u64 key = slot.pc.load(std::memory_order_relaxed);
            if (key == guest_pc) {
                slot.samples.fetch_add(1, std::memory_order_relaxed);
                slot.sample_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
                return;
            }
            if (key == 0) {
                u64 expected = 0;
                if (slot.pc.compare_exchange_strong(expected, guest_pc,
                                                    std::memory_order_relaxed,
                                                    std::memory_order_relaxed) ||
                    expected == guest_pc) {
                    slot.samples.fetch_add(1, std::memory_order_relaxed);
                    slot.sample_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
                    return;
                }
            }
            slot_index = (slot_index + 1) & (PcSlotCount - 1);
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
    static constexpr size_t PcSlotCount = 512;
    static constexpr size_t PcProbeCount = 8;
    static constexpr size_t PcReportTopCount = 12;
    static_assert((PcSlotCount & (PcSlotCount - 1)) == 0);

    struct PcSlot {
        std::atomic<u64> pc{0};
        std::atomic<u64> samples{0};
        std::atomic<u64> sample_ns{0};
    };

    struct ProducerState {
        std::array<PcSlot, PcSlotCount> slots{};
        std::atomic<u64> dropped_samples{0};
    };

    struct PcDelta {
        u64 pc{};
        u64 samples{};
        u64 sample_ns{};
    };

    static size_t PcHash(u64 guest_pc) noexcept {
        constexpr u64 Golden = 0x9e3779b97f4a7c15ULL;
        return static_cast<size_t>(((guest_pc >> 2) * Golden) & (PcSlotCount - 1));
    }

    static u64 Avg(u64 total, u64 count) noexcept {
        return count == 0 ? 0 : total / count;
    }

    void ReportProducer(u64 frame, u64 frames, size_t producer_index) noexcept {
        auto& producer = producers[producer_index];
        std::array<PcDelta, PcSlotCount> deltas{};
        size_t delta_count = 0;
        size_t occupied = 0;
        u64 total_samples = 0;
        u64 total_ns = 0;

        for (size_t slot_index = 0; slot_index < PcSlotCount; ++slot_index) {
            const auto& slot = producer.slots[slot_index];
            const u64 pc = slot.pc.load(std::memory_order_relaxed);
            if (pc != 0) {
                ++occupied;
            }
            const u64 samples = slot.samples.load(std::memory_order_relaxed);
            const u64 sample_ns = slot.sample_ns.load(std::memory_order_relaxed);
            const u64 previous_sample_count = previous_samples[producer_index][slot_index];
            const u64 previous_sample_ns = previous_ns[producer_index][slot_index];
            previous_samples[producer_index][slot_index] = samples;
            previous_ns[producer_index][slot_index] = sample_ns;

            const u64 delta_samples = samples - previous_sample_count;
            const u64 delta_ns = sample_ns - previous_sample_ns;
            if (pc == 0 || delta_samples == 0) {
                continue;
            }
            deltas[delta_count++] = PcDelta{pc, delta_samples, delta_ns};
            total_samples += delta_samples;
            total_ns += delta_ns;
        }

        std::sort(deltas.begin(), deltas.begin() + static_cast<std::ptrdiff_t>(delta_count),
                  [](const PcDelta& lhs, const PcDelta& rhs) {
                      if (lhs.sample_ns != rhs.sample_ns) {
                          return lhs.sample_ns > rhs.sample_ns;
                      }
                      return lhs.samples > rhs.samples;
                  });

        const size_t top_count = std::min(delta_count, PcReportTopCount);
        u64 top_samples = 0;
        u64 top_ns = 0;
        for (size_t i = 0; i < top_count; ++i) {
            top_samples += deltas[i].samples;
            top_ns += deltas[i].sample_ns;
        }

        const u64 dropped_now = producer.dropped_samples.load(std::memory_order_relaxed);
        const u64 dropped_delta = dropped_now - previous_dropped[producer_index];
        previous_dropped[producer_index] = dropped_now;
        const u64 coverage_permille = total_ns == 0 ? 0 : top_ns * 1000 / total_ns;

        LOG_INFO(HW_GPU,
                 "[X1-XEXCLPC] frame={} frames={} producer={} summary sampleRate={} samples={} "
                 "sampleNs={} topSamples={} topNs={} coveragePermille={} dropped={} occupied={}",
                 frame, frames, producer_index, SampleRate, total_samples, total_ns, top_samples,
                 top_ns, coverage_permille, dropped_delta, occupied);

        for (size_t rank = 0; rank < top_count; ++rank) {
            const auto& entry = deltas[rank];
            LOG_INFO(HW_GPU,
                     "[X1-XEXCLPC] frame={} frames={} producer={} rank={} pc={:#x} samples={} "
                     "sampleNs={} sampleAvgNs={}",
                     frame, frames, producer_index, rank, entry.pc, entry.samples, entry.sample_ns,
                     Avg(entry.sample_ns, entry.samples));
        }
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    std::array<ProducerState, ProducerCount> producers{};
    std::array<std::array<u64, PcSlotCount>, ProducerCount> previous_samples{};
    std::array<std::array<u64, PcSlotCount>, ProducerCount> previous_ns{};
    std::array<u64, ProducerCount> previous_dropped{};
};

} // namespace Core
