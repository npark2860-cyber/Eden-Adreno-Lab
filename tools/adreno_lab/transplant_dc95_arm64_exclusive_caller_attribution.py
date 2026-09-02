#!/usr/bin/env python3
# Add sampled higher-level LockMutex caller attribution on top of the validated LDXR PC profiler.

from pathlib import Path
import shutil
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: transplant_dc95_arm64_exclusive_caller_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    lab_root = Path(__file__).resolve().parents[2]
    caller_profiler_source = lab_root / "src/core/x1_arm64_exclusive_caller_profiler.h"
    caller_profiler_target = root / "src/core/x1_arm64_exclusive_caller_profiler.h"
    if not caller_profiler_source.exists():
        raise RuntimeError("ARM64 exclusive caller profiler source header missing")
    shutil.copyfile(caller_profiler_source, caller_profiler_target)

    # 1) The exact ARM64 backend already keeps the current guest SP in A64JitState::sp.
    # Pass it as X3 to the existing diagnostic exclusive-read trampoline. No IR/opcode change.
    emit_memory = root / "src/dynarmic/src/dynarmic/backend/arm64/emit_arm64_memory.cpp"
    text = emit_memory.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "dynarmic/backend/arm64/abi.h"\n',
        '#include "dynarmic/backend/arm64/abi.h"\n'
        '#include "dynarmic/backend/arm64/a64_jitstate.h"\n',
        "A64 JIT state include",
    )
    text = replace_once(
        text,
        '''    ctx.reg_alloc.PrepareForCall({}, args[1], args[0]);
    const bool ordered = IsOrdered(args[2].GetImmediateAccType());
''',
        '''    ctx.reg_alloc.PrepareForCall({}, args[1], args[0]);
    code.LDR(X3, Xstate, offsetof(A64JitState, sp));
    const bool ordered = IsOrdered(args[2].GetImmediateAccType());
''',
        "exclusive-read guest SP argument",
    )
    emit_memory.write_text(text, encoding="utf-8")

    # 2) Extend only the diagnostic callback with the guest SP.
    config = root / "src/dynarmic/src/dynarmic/interface/A64/config.h"
    text = config.read_text(encoding="utf-8")
    old = '''    virtual void RecordExclusiveReadProfile(std::int32_t /*profile_index*/,
                                            std::uint32_t /*bitsize*/,
                                            std::uint64_t /*elapsed_ns*/,
                                            std::uint64_t /*guest_pc*/) {}
'''
    new = '''    virtual void RecordExclusiveReadProfile(std::int32_t /*profile_index*/,
                                            std::uint32_t /*bitsize*/,
                                            std::uint64_t /*elapsed_ns*/,
                                            std::uint64_t /*guest_pc*/,
                                            std::uint64_t /*guest_sp*/) {}
'''
    text = replace_once(text, old, new, "A64 exclusive-read guest SP hook")
    config.write_text(text, encoding="utf-8")

    # 3) Thread guest SP through the existing ARM64 trampoline without touching ReadAndMark.
    address_space = root / "src/dynarmic/src/dynarmic/backend/arm64/a64_address_space.cpp"
    text = address_space.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr,
                     u64 location_descriptor) -> T {
''',
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr,
                     u64 location_descriptor, u64 guest_sp) -> T {
''',
        "generic exclusive-read guest SP trampoline",
    )
    text = replace_once(
        text,
        '''        conf.callbacks->RecordExclusiveReadProfile(
            profile_index, static_cast<std::uint32_t>(sizeof(T) * 8), elapsed_ns, guest_pc);
''',
        '''        conf.callbacks->RecordExclusiveReadProfile(
            profile_index, static_cast<std::uint32_t>(sizeof(T) * 8), elapsed_ns, guest_pc,
            guest_sp);
''',
        "generic exclusive-read guest SP record",
    )
    text = replace_once(
        text,
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr,
                     u64 location_descriptor) -> Vector {
''',
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr,
                     u64 location_descriptor, u64 guest_sp) -> Vector {
''',
        "128-bit exclusive-read guest SP trampoline",
    )
    text = replace_once(
        text,
        '''        conf.callbacks->RecordExclusiveReadProfile(profile_index, 128, elapsed_ns, guest_pc);
''',
        '''        conf.callbacks->RecordExclusiveReadProfile(profile_index, 128, elapsed_ns, guest_pc,
                                                    guest_sp);
''',
        "128-bit exclusive-read guest SP record",
    )
    address_space.write_text(text, encoding="utf-8")

    # 4) Keep existing exact totals + 1/16 PC samples, and independently sample only the
    # sdk+0x131754 Enter LDAXR at 1/64. At that exact instruction the saved higher-level
    # LockMutex caller LR is at guest SP + 0x38 for this SDK build.
    arm_h = root / "src/core/arm/dynarmic/arm_dynarmic_64.h"
    text = arm_h.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    void RecordExclusiveReadProfile(std::int32_t profile_index, std::uint32_t bitsize,
                                    std::uint64_t elapsed_ns, std::uint64_t guest_pc) override;
''',
        '''    void RecordExclusiveReadProfile(std::int32_t profile_index, std::uint32_t bitsize,
                                    std::uint64_t elapsed_ns, std::uint64_t guest_pc,
                                    std::uint64_t guest_sp) override;
''',
        "DynarmicCallbacks64 caller declaration",
    )
    text = replace_once(
        text,
        '''    u32 m_x1_exclusive_pc_sample_state{0x9e3779b9U};
    static constexpr u64 MinimumRunCycles = 10000U;
''',
        '''    u32 m_x1_exclusive_pc_sample_state{0x9e3779b9U};
    u32 m_x1_exclusive_caller_sample_state{0x243f6a88U};
    static constexpr u64 MinimumRunCycles = 10000U;
''',
        "DynarmicCallbacks64 caller sample state",
    )
    arm_h.write_text(text, encoding="utf-8")

    arm_cpp = root / "src/core/arm/dynarmic/arm_dynarmic_64.cpp"
    text = arm_cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_arm64_exclusive_pc_profiler.h"\n',
        '#include "core/x1_arm64_exclusive_pc_profiler.h"\n'
        '#include "core/x1_arm64_exclusive_caller_profiler.h"\n',
        "ARM64 exclusive caller profiler include",
    )
    old = '''void DynarmicCallbacks64::RecordExclusiveReadProfile(std::int32_t profile_index,
                                                      std::uint32_t bitsize,
                                                      std::uint64_t elapsed_ns,
                                                      std::uint64_t guest_pc) {
    if (profile_index < 0) {
        return;
    }
    X1Arm64ExclusiveProfiler::Get().RecordRead(static_cast<u32>(profile_index), bitsize,
                                               elapsed_ns);

    if (bitsize != 32 || guest_pc == 0) {
        return;
    }
    m_x1_exclusive_pc_sample_state =
        m_x1_exclusive_pc_sample_state * 1664525U + 1013904223U;
    if ((m_x1_exclusive_pc_sample_state &
         (X1Arm64ExclusivePcProfiler::SampleRate - 1U)) != 0) {
        return;
    }
    X1Arm64ExclusivePcProfiler::Get().RecordReadSample(static_cast<u32>(profile_index), guest_pc,
                                                       elapsed_ns);
}
'''
    new = '''void DynarmicCallbacks64::RecordExclusiveReadProfile(std::int32_t profile_index,
                                                      std::uint32_t bitsize,
                                                      std::uint64_t elapsed_ns,
                                                      std::uint64_t guest_pc,
                                                      std::uint64_t guest_sp) {
    if (profile_index < 0) {
        return;
    }
    const u32 producer_index = static_cast<u32>(profile_index);
    X1Arm64ExclusiveProfiler::Get().RecordRead(producer_index, bitsize, elapsed_ns);

    if (bitsize != 32 || guest_pc == 0) {
        return;
    }

    m_x1_exclusive_pc_sample_state =
        m_x1_exclusive_pc_sample_state * 1664525U + 1013904223U;
    if ((m_x1_exclusive_pc_sample_state &
         (X1Arm64ExclusivePcProfiler::SampleRate - 1U)) == 0) {
        X1Arm64ExclusivePcProfiler::Get().RecordReadSample(producer_index, guest_pc, elapsed_ns);
    }

    auto& caller_profiler = X1Arm64ExclusiveCallerProfiler::Get();
    if (guest_sp == 0 || !caller_profiler.IsTargetEnterPc(guest_pc)) {
        return;
    }
    m_x1_exclusive_caller_sample_state =
        m_x1_exclusive_caller_sample_state * 1664525U + 1013904223U;
    if ((m_x1_exclusive_caller_sample_state &
         (X1Arm64ExclusiveCallerProfiler::SampleRate - 1U)) != 0) {
        return;
    }

    constexpr u64 CallerOffset = X1Arm64ExclusiveCallerProfiler::LockMutexCallerLrStackOffset;
    if (guest_sp > std::numeric_limits<u64>::max() - CallerOffset) {
        caller_profiler.RecordInvalidStack(producer_index);
        return;
    }
    const u64 caller_address = guest_sp + CallerOffset;
    if (!m_memory.IsValidVirtualAddressRange(caller_address, sizeof(u64))) {
        caller_profiler.RecordInvalidStack(producer_index);
        return;
    }
    const u64 caller_lr = m_memory.Read64(caller_address);
    if (caller_lr == 0) {
        caller_profiler.RecordInvalidStack(producer_index);
        return;
    }
    caller_profiler.RecordCallerSample(producer_index, caller_lr);
}
'''
    text = replace_once(text, old, new, "DynarmicCallbacks64 exclusive caller implementation")
    # std::numeric_limits is used only by this low-rate observation hook.
    text = replace_once(text, '#include <memory>\n', '#include <memory>\n#include <limits>\n',
                        "ARM64 caller numeric limits include")
    arm_cpp.write_text(text, encoding="utf-8")

    # 5) Register the exact SDK runtime range from the existing loader path.
    loader = root / "src/core/loader/deconstructed_rom_directory.cpp"
    text = loader.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_waker_stage_k_profiler.h"\n',
        '#include "core/x1_waker_stage_k_profiler.h"\n'
        '#include "core/x1_arm64_exclusive_caller_profiler.h"\n',
        "exclusive caller loader include",
    )
    main_registration = '''        if (std::strcmp(module, "main") == 0) {
            Core::X1WakerStageKProfiler::Get().RegisterMainModuleRange(load_addr, next_load_addr);
        }
'''
    caller_registration = main_registration + '''        if (std::strcmp(module, "sdk") == 0) {
            Core::X1Arm64ExclusiveCallerProfiler::Get().RegisterSdkModuleRange(load_addr,
                                                                               next_load_addr);
        }
'''
    text = replace_once(text, main_registration, caller_registration,
                        "exclusive caller SDK range registration")
    loader.write_text(text, encoding="utf-8")

    # 6) Reuse the same Qualcomm gate and 120-frame report boundary.
    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_arm64_exclusive_pc_profiler.h"\n',
        '#include "core/x1_arm64_exclusive_pc_profiler.h"\n'
        '#include "core/x1_arm64_exclusive_caller_profiler.h"\n',
        "exclusive caller rasterizer include",
    )
    text = replace_once(
        text,
        '''    Core::X1Arm64ExclusivePcProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
''',
        '''    Core::X1Arm64ExclusivePcProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    Core::X1Arm64ExclusiveCallerProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
''',
        "exclusive caller profiler initialization",
    )
    text = replace_once(
        text,
        '''    Core::X1Arm64ExclusivePcProfiler::Get().FrameEnd();
''',
        '''    Core::X1Arm64ExclusivePcProfiler::Get().FrameEnd();
    Core::X1Arm64ExclusiveCallerProfiler::Get().FrameEnd();
''',
        "exclusive caller profiler frame boundary",
    )
    rasterizer.write_text(text, encoding="utf-8")

    # Observation-only invariants.
    final_emit = emit_memory.read_text(encoding="utf-8")
    if final_emit.count("offsetof(A64JitState, sp)") != 1:
        raise RuntimeError("exclusive caller guest SP load count mismatch")
    final_address = address_space.read_text(encoding="utf-8")
    if final_address.count("global_monitor->ReadAndMark<T>") != 1:
        raise RuntimeError("generic ReadAndMark semantics changed")
    if final_address.count("global_monitor->ReadAndMark<Vector>") != 1:
        raise RuntimeError("128-bit ReadAndMark semantics changed")
    if final_address.count("guest_sp) -> T") != 1 or final_address.count("guest_sp) -> Vector") != 1:
        raise RuntimeError("exclusive caller trampoline guest SP shape mismatch")
    final_arm = arm_cpp.read_text(encoding="utf-8")
    if final_arm.count("RecordReadSample") != 1:
        raise RuntimeError("existing exclusive PC sampler shape changed")
    if final_arm.count("RecordCallerSample") != 1:
        raise RuntimeError("exclusive caller sample shape mismatch")
    if final_arm.count("IsValidVirtualAddressRange(caller_address, sizeof(u64))") != 1:
        raise RuntimeError("exclusive caller stack safety check missing")
    final_loader = loader.read_text(encoding="utf-8")
    if final_loader.count("RegisterSdkModuleRange") != 1:
        raise RuntimeError("exclusive caller SDK range registration mismatch")
    if not caller_profiler_target.exists():
        raise RuntimeError("exclusive caller profiler header was not copied")

    print("Transplanted exact dc95 ARM64 exclusive critical-section caller attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
