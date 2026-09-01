#!/usr/bin/env python3
# Observation-only attribution of ARM64 Dynarmic exclusive-write/STXR handling for Stage F producers.

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_arm64_exclusive_callback_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    profiler = root / "src/core/x1_arm64_exclusive_profiler.h"
    if not profiler.exists():
        raise RuntimeError("x1_arm64_exclusive_profiler.h must be copied before this pass")

    # 1) Add two no-op-by-default observation hooks to Dynarmic A64 callbacks.
    config = root / "src/dynarmic/src/dynarmic/interface/A64/config.h"
    text = config.read_text(encoding="utf-8")
    exclusive_anchor = '''    virtual bool MemoryWriteExclusive128(VAddr /*vaddr*/, Vector /*value*/, Vector /*expected*/) { return false; }
'''
    exclusive_replacement = exclusive_anchor + '''
    // Optional host-side observation hook for an exclusive-write operation. These hooks are
    // diagnostic only and must not participate in guest-visible exclusive semantics.
    virtual std::int32_t GetExclusiveWriteProfileIndex() { return -1; }
    virtual void RecordExclusiveWriteProfile(std::int32_t /*profile_index*/,
                                             std::uint32_t /*bitsize*/, bool /*success*/,
                                             std::uint64_t /*elapsed_ns*/) {}
'''
    text = replace_once(text, exclusive_anchor, exclusive_replacement,
                        "Dynarmic A64 exclusive observation hooks")
    config.write_text(text, encoding="utf-8")

    # 2) Observe the final DoExclusiveOperation result, including monitor-level failures that
    # never reach MemoryWriteExclusive*. Time only already-selected Stage F producers.
    address_space = root / "src/dynarmic/src/dynarmic/backend/arm64/a64_address_space.cpp"
    text = address_space.read_text(encoding="utf-8")
    text = replace_once(text, '#include <bit>\n', '#include <bit>\n#include <chrono>\n',
                        "ARM64 exclusive chrono include")

    generic_old = '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr, T value) -> u32 {
        return conf.global_monitor->DoExclusiveOperation<T>(conf.processor_id, vaddr,
                                                            [&](T expected) -> bool {
                                                                return (conf.callbacks->*callback)(vaddr, value, expected);
                                                            })
                 ? 0
                 : 1;
    };
'''
    generic_new = '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr, T value) -> u32 {
        const auto run_exclusive = [&]() -> bool {
            return conf.global_monitor->DoExclusiveOperation<T>(
                conf.processor_id, vaddr, [&](T expected) -> bool {
                    return (conf.callbacks->*callback)(vaddr, value, expected);
                });
        };

        const std::int32_t profile_index = conf.callbacks->GetExclusiveWriteProfileIndex();
        if (profile_index < 0) {
            return run_exclusive() ? 0 : 1;
        }

        const auto start = std::chrono::steady_clock::now();
        const bool success = run_exclusive();
        const auto end = std::chrono::steady_clock::now();
        const auto elapsed_ns = static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count());
        conf.callbacks->RecordExclusiveWriteProfile(
            profile_index, static_cast<std::uint32_t>(sizeof(T) * 8), success, elapsed_ns);
        return success ? 0 : 1;
    };
'''
    text = replace_once(text, generic_old, generic_new,
                        "generic ARM64 exclusive-write result observation")

    vector_old = '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr, Vector value) -> u32 {
        return conf.global_monitor->DoExclusiveOperation<Vector>(conf.processor_id, vaddr,
                                                                 [&](Vector expected) -> bool {
                                                                     return conf.callbacks->MemoryWriteExclusive128(vaddr, value, expected);
                                                                 })
                 ? 0
                 : 1;
    };
'''
    vector_new = '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr, Vector value) -> u32 {
        const auto run_exclusive = [&]() -> bool {
            return conf.global_monitor->DoExclusiveOperation<Vector>(
                conf.processor_id, vaddr, [&](Vector expected) -> bool {
                    return conf.callbacks->MemoryWriteExclusive128(vaddr, value, expected);
                });
        };

        const std::int32_t profile_index = conf.callbacks->GetExclusiveWriteProfileIndex();
        if (profile_index < 0) {
            return run_exclusive() ? 0 : 1;
        }

        const auto start = std::chrono::steady_clock::now();
        const bool success = run_exclusive();
        const auto end = std::chrono::steady_clock::now();
        const auto elapsed_ns = static_cast<std::uint64_t>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count());
        conf.callbacks->RecordExclusiveWriteProfile(profile_index, 128, success, elapsed_ns);
        return success ? 0 : 1;
    };
'''
    text = replace_once(text, vector_old, vector_new,
                        "128-bit ARM64 exclusive-write result observation")
    address_space.write_text(text, encoding="utf-8")

    # 3) Keep producer selection outside the hot exclusive path. RunThread already knows the
    # currently executing KThread, so resolve Stage F producer identity once per JIT run slice.
    arm_h = root / "src/core/arm/dynarmic/arm_dynarmic_64.h"
    text = arm_h.read_text(encoding="utf-8")
    hook_decl_anchor = '''    bool MemoryWriteExclusive128(u64 vaddr, Dynarmic::A64::Vector value, Dynarmic::A64::Vector expected) override;
'''
    hook_decl_replacement = hook_decl_anchor + '''    std::int32_t GetExclusiveWriteProfileIndex() override;
    void RecordExclusiveWriteProfile(std::int32_t profile_index, std::uint32_t bitsize,
                                     bool success, std::uint64_t elapsed_ns) override;
    void SetX1ExclusiveProducerIndex(s32 producer_index) noexcept {
        m_x1_exclusive_producer_index = producer_index;
    }
'''
    text = replace_once(text, hook_decl_anchor, hook_decl_replacement,
                        "DynarmicCallbacks64 exclusive profiler overrides")

    member_anchor = '''    const bool m_check_memory_access{};
    static constexpr u64 MinimumRunCycles = 10000U;
'''
    member_replacement = '''    const bool m_check_memory_access{};
    s32 m_x1_exclusive_producer_index{-1};
    static constexpr u64 MinimumRunCycles = 10000U;
'''
    text = replace_once(text, member_anchor, member_replacement,
                        "DynarmicCallbacks64 selected producer state")
    arm_h.write_text(text, encoding="utf-8")

    arm_cpp = root / "src/core/arm/dynarmic/arm_dynarmic_64.cpp"
    text = arm_cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/hle/kernel/k_process.h"\n',
        '#include "core/hle/kernel/k_process.h"\n'
        '#include "core/hle/kernel/k_thread.h"\n'
        '#include "core/x1_arm64_exclusive_profiler.h"\n'
        '#include "core/x1_waker_stage_f_profiler.h"\n',
        "ARM64 exclusive profiler includes",
    )

    exclusive_impl_anchor = '''bool DynarmicCallbacks64::MemoryWriteExclusive128(u64 vaddr, Dynarmic::A64::Vector value, Dynarmic::A64::Vector expected) {
    return CheckMemoryAccess(vaddr, 16, Kernel::DebugWatchpointType::Write) &&
            m_memory.WriteExclusive128(vaddr, value, expected);
}
'''
    exclusive_impl_replacement = exclusive_impl_anchor + '''
std::int32_t DynarmicCallbacks64::GetExclusiveWriteProfileIndex() {
    return m_x1_exclusive_producer_index;
}

void DynarmicCallbacks64::RecordExclusiveWriteProfile(std::int32_t profile_index,
                                                       std::uint32_t bitsize, bool success,
                                                       std::uint64_t elapsed_ns) {
    if (profile_index < 0) {
        return;
    }
    X1Arm64ExclusiveProfiler::Get().Record(static_cast<u32>(profile_index), bitsize, success,
                                           elapsed_ns);
}
'''
    text = replace_once(text, exclusive_impl_anchor, exclusive_impl_replacement,
                        "ARM64 exclusive profiler callback implementation")

    run_old = '''HaltReason ArmDynarmic64::RunThread(Kernel::KThread* thread) {
    m_jit->ClearExclusiveState();
    return TranslateHaltReason(m_jit->Run());
}
'''
    run_new = '''HaltReason ArmDynarmic64::RunThread(Kernel::KThread* thread) {
    const s32 x1_exclusive_producer_index =
        X1WakerStageFProfiler::Get().GetTrackedProducerIndex(thread->GetThreadId());
    m_cb->SetX1ExclusiveProducerIndex(x1_exclusive_producer_index);
    m_jit->ClearExclusiveState();
    const HaltReason result = TranslateHaltReason(m_jit->Run());
    m_cb->SetX1ExclusiveProducerIndex(-1);
    return result;
}
'''
    text = replace_once(text, run_old, run_new,
                        "selected producer identity once per Dynarmic run slice")
    arm_cpp.write_text(text, encoding="utf-8")

    # 4) Reuse the Stage K/F Qualcomm logging gate and exact 120-frame reporting boundary.
    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_k_profiler.h"\n',
        '#include "core/x1_waker_stage_k_profiler.h"\n'
        '#include "core/x1_arm64_exclusive_profiler.h"\n',
        "ARM64 exclusive profiler rasterizer include",
    )

    init_anchor = '''    Core::X1WakerStageKProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    init_replacement = init_anchor + '''    Core::X1Arm64ExclusiveProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
'''
    text = replace_once(text, init_anchor, init_replacement,
                        "ARM64 exclusive profiler initialization")

    frame_anchor = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1WakerStageKProfiler::Get().FrameEnd();
    Core::X1WakerStageJProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    frame_replacement = '''    Core::X1WakerStageEProfiler::Get().FrameEnd();
    Core::X1Arm64ExclusiveProfiler::Get().FrameEnd();
    Core::X1WakerStageKProfiler::Get().FrameEnd();
    Core::X1WakerStageJProfiler::Get().FrameEnd();
    Core::X1WakerStageGProfiler::Get().FrameEnd();
    Core::X1WakerStageFProfiler::Get().FrameEnd();
'''
    text = replace_once(text, frame_anchor, frame_replacement,
                        "ARM64 exclusive report before Stage F identity rotation")
    rasterizer.write_text(text, encoding="utf-8")

    checks = {
        profiler: [
            "[X1-XEXCL]", "ProducerCount = 2", "ReportFrames = 120", "callbackNs=",
            "s32=", "Record(u32 producer_index, u32 bitsize, bool success, u64 elapsed_ns)",
        ],
        config: ["GetExclusiveWriteProfileIndex", "RecordExclusiveWriteProfile"],
        address_space: [
            "std::chrono::steady_clock::now", "DoExclusiveOperation<T>",
            "DoExclusiveOperation<Vector>", "RecordExclusiveWriteProfile",
            "profile_index < 0",
        ],
        arm_h: [
            "GetExclusiveWriteProfileIndex() override", "RecordExclusiveWriteProfile",
            "m_x1_exclusive_producer_index{-1}",
        ],
        arm_cpp: [
            "GetTrackedProducerIndex(thread->GetThreadId())", "SetX1ExclusiveProducerIndex",
            "X1Arm64ExclusiveProfiler::Get().Record", "m_jit->Run()",
        ],
        rasterizer: [
            "X1Arm64ExclusiveProfiler::Get().Initialize",
            "X1Arm64ExclusiveProfiler::Get().FrameEnd",
        ],
    }
    for path, markers in checks.items():
        final = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in final:
                raise RuntimeError(f"{path}: required marker missing: {marker}")

    final_address_space = address_space.read_text(encoding="utf-8")
    if final_address_space.count("GetExclusiveWriteProfileIndex()") != 2:
        raise RuntimeError("exclusive profiling must cover generic and 128-bit write trampolines only")
    if final_address_space.count("RecordExclusiveWriteProfile(") != 2:
        raise RuntimeError("exclusive profiling record hook count mismatch")
    if final_address_space.count("DoExclusiveOperation<T>") != 1:
        raise RuntimeError("generic exclusive semantics duplicated or removed")
    if final_address_space.count("DoExclusiveOperation<Vector>") != 1:
        raise RuntimeError("128-bit exclusive semantics duplicated or removed")

    final_arm_cpp = arm_cpp.read_text(encoding="utf-8")
    run_start = final_arm_cpp.index("HaltReason ArmDynarmic64::RunThread")
    run_end = final_arm_cpp.index("HaltReason ArmDynarmic64::StepThread", run_start)
    run_block = final_arm_cpp[run_start:run_end]
    if run_block.count("m_jit->Run()") != 1:
        raise RuntimeError("RunThread execution count changed")
    if run_block.count("ClearExclusiveState()") != 1:
        raise RuntimeError("RunThread exclusive-state clearing changed")
    if run_block.count("GetTrackedProducerIndex") != 1:
        raise RuntimeError("producer identity must be resolved exactly once per RunThread")

    raw = "\n".join(path.read_text(encoding="utf-8") for path in checks)
    for forbidden in (
        "SetPriority(", "SetCoreMask(", "Reschedule(", "YieldTo(", "sleep_for", "sleep_until",
        "QueueBuffer(", "swap_interval =", "gpu_fence_behavior",
    ):
        if forbidden in raw:
            raise RuntimeError(f"behavior-changing token found in exclusive profiler patch: {forbidden}")

    print("Transplanted dc95 ARM64 selected-producer exclusive callback attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
