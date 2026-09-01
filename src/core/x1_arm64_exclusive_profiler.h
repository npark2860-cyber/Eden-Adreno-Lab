// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <cstddef>

#include "common/common_types.h"
#include "common/logging.h"
#include "common/settings.h"

namespace Core {

class X1Arm64ExclusiveProfiler final {
public:
    static X1Arm64ExclusiveProfiler& Get() {
        static X1Arm64ExclusiveProfiler profiler;
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
        for (auto& producer : producers) {
            ResetProducer(producer);
        }
    }

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled.load(std::memory_order_relaxed);
    }

    void Record(u32 producer_index, u32 bitsize, bool success, u64 elapsed_ns) noexcept {
        if (!Enabled() || producer_index >= ProducerCount) {
            return;
        }

        const u32 size_index = SizeIndex(bitsize);
        auto& producer = producers[producer_index];
        producer.attempts.fetch_add(1, std::memory_order_relaxed);
        producer.callback_ns.fetch_add(elapsed_ns, std::memory_order_relaxed);
        AtomicMax(producer.callback_max_ns, elapsed_ns);
        if (success) {
            producer.success.fetch_add(1, std::memory_order_relaxed);
        } else {
            producer.failure.fetch_add(1, std::memory_order_relaxed);
        }

        if (size_index >= SizeClassCount) {
            producer.bad_size.fetch_add(1, std::memory_order_relaxed);
            return;
        }

        producer.size_attempts[size_index].fetch_add(1, std::memory_order_relaxed);
        producer.size_callback_ns[size_index].fetch_add(elapsed_ns, std::memory_order_relaxed);
        if (success) {
            producer.size_success[size_index].fetch_add(1, std::memory_order_relaxed);
        } else {
            producer.size_failure[size_index].fetch_add(1, std::memory_order_relaxed);
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

        for (size_t producer_index = 0; producer_index < ProducerCount; ++producer_index) {
            const auto snapshot = SnapshotAndReset(producers[producer_index]);
            LOG_INFO(
                HW_GPU,
                "[X1-XEXCL] frame={} frames={} producer={} attempts={} success={} fail={} "
                "callbackNs={} callbackAvgNs={} callbackMaxNs={} badSize={} "
                "s8={}/{}/{}/{} s16={}/{}/{}/{} s32={}/{}/{}/{} "
                "s64={}/{}/{}/{} s128={}/{}/{}/{}",
                frame, frames, producer_index, snapshot.attempts, snapshot.success,
                snapshot.failure, snapshot.callback_ns, Avg(snapshot.callback_ns, snapshot.attempts),
                snapshot.callback_max_ns, snapshot.bad_size,
                snapshot.size_attempts[0], snapshot.size_success[0], snapshot.size_failure[0],
                snapshot.size_callback_ns[0], snapshot.size_attempts[1], snapshot.size_success[1],
                snapshot.size_failure[1], snapshot.size_callback_ns[1], snapshot.size_attempts[2],
                snapshot.size_success[2], snapshot.size_failure[2], snapshot.size_callback_ns[2],
                snapshot.size_attempts[3], snapshot.size_success[3], snapshot.size_failure[3],
                snapshot.size_callback_ns[3], snapshot.size_attempts[4], snapshot.size_success[4],
                snapshot.size_failure[4], snapshot.size_callback_ns[4]);
        }
    }

private:
    static constexpr u64 ReportFrames = 120;
    static constexpr size_t ProducerCount = 2;
    static constexpr size_t SizeClassCount = 5;

    struct ProducerState {
        std::atomic<u64> attempts{0};
        std::atomic<u64> success{0};
        std::atomic<u64> failure{0};
        std::atomic<u64> callback_ns{0};
        std::atomic<u64> callback_max_ns{0};
        std::atomic<u64> bad_size{0};
        std::array<std::atomic<u64>, SizeClassCount> size_attempts{};
        std::array<std::atomic<u64>, SizeClassCount> size_success{};
        std::array<std::atomic<u64>, SizeClassCount> size_failure{};
        std::array<std::atomic<u64>, SizeClassCount> size_callback_ns{};
    };

    struct ProducerSnapshot {
        u64 attempts{};
        u64 success{};
        u64 failure{};
        u64 callback_ns{};
        u64 callback_max_ns{};
        u64 bad_size{};
        std::array<u64, SizeClassCount> size_attempts{};
        std::array<u64, SizeClassCount> size_success{};
        std::array<u64, SizeClassCount> size_failure{};
        std::array<u64, SizeClassCount> size_callback_ns{};
    };

    static u32 SizeIndex(u32 bitsize) noexcept {
        switch (bitsize) {
        case 8:
            return 0;
        case 16:
            return 1;
        case 32:
            return 2;
        case 64:
            return 3;
        case 128:
            return 4;
        default:
            return static_cast<u32>(SizeClassCount);
        }
    }

    static u64 Avg(u64 total, u64 count) noexcept {
        return count == 0 ? 0 : total / count;
    }

    static void AtomicMax(std::atomic<u64>& target, u64 value) noexcept {
        u64 current = target.load(std::memory_order_relaxed);
        while (current < value &&
               !target.compare_exchange_weak(current, value, std::memory_order_relaxed,
                                             std::memory_order_relaxed)) {
        }
    }

    static void ResetProducer(ProducerState& producer) noexcept {
        producer.attempts.store(0, std::memory_order_relaxed);
        producer.success.store(0, std::memory_order_relaxed);
        producer.failure.store(0, std::memory_order_relaxed);
        producer.callback_ns.store(0, std::memory_order_relaxed);
        producer.callback_max_ns.store(0, std::memory_order_relaxed);
        producer.bad_size.store(0, std::memory_order_relaxed);
        for (size_t i = 0; i < SizeClassCount; ++i) {
            producer.size_attempts[i].store(0, std::memory_order_relaxed);
            producer.size_success[i].store(0, std::memory_order_relaxed);
            producer.size_failure[i].store(0, std::memory_order_relaxed);
            producer.size_callback_ns[i].store(0, std::memory_order_relaxed);
        }
    }

    static ProducerSnapshot SnapshotAndReset(ProducerState& producer) noexcept {
        ProducerSnapshot snapshot{};
        snapshot.attempts = producer.attempts.exchange(0, std::memory_order_relaxed);
        snapshot.success = producer.success.exchange(0, std::memory_order_relaxed);
        snapshot.failure = producer.failure.exchange(0, std::memory_order_relaxed);
        snapshot.callback_ns = producer.callback_ns.exchange(0, std::memory_order_relaxed);
        snapshot.callback_max_ns = producer.callback_max_ns.exchange(0, std::memory_order_relaxed);
        snapshot.bad_size = producer.bad_size.exchange(0, std::memory_order_relaxed);
        for (size_t i = 0; i < SizeClassCount; ++i) {
            snapshot.size_attempts[i] =
                producer.size_attempts[i].exchange(0, std::memory_order_relaxed);
            snapshot.size_success[i] =
                producer.size_success[i].exchange(0, std::memory_order_relaxed);
            snapshot.size_failure[i] =
                producer.size_failure[i].exchange(0, std::memory_order_relaxed);
            snapshot.size_callback_ns[i] =
                producer.size_callback_ns[i].exchange(0, std::memory_order_relaxed);
        }
        return snapshot;
    }

    std::atomic<bool> enabled{false};
    std::atomic<u64> frame_id{0};
    u64 frames_since_report{};
    std::array<ProducerState, ProducerCount> producers{};
};

} // namespace Core
