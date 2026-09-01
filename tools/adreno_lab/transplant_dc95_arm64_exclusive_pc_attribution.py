#!/usr/bin/env python3
# Add exact guest-PC attribution to the already-applied ARM64 exclusive read profiler.

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
        raise SystemExit("usage: transplant_dc95_arm64_exclusive_pc_attribution.py <eden-root>")

    root = Path(sys.argv[1])
    lab_root = Path(__file__).resolve().parents[2]
    pc_profiler_source = lab_root / "src/core/x1_arm64_exclusive_pc_profiler.h"
    pc_profiler_target = root / "src/core/x1_arm64_exclusive_pc_profiler.h"
    if not pc_profiler_source.exists():
        raise RuntimeError("ARM64 exclusive PC profiler source header missing")
    shutil.copyfile(pc_profiler_source, pc_profiler_target)

    # 1) Preserve the exact A64 location descriptor as a third integer argument for LDXR callbacks.
    emit_memory = root / "src/dynarmic/src/dynarmic/backend/arm64/emit_arm64_memory.cpp"
    text = emit_memory.read_text(encoding="utf-8")
    old = '''template<std::size_t bitsize>
void CallbackOnlyEmitExclusiveReadMemory(oaknut::CodeGenerator& code, EmitContext& ctx, IR::Inst* inst) {
    auto args = ctx.reg_alloc.GetArgumentInfo(inst);
    ctx.reg_alloc.PrepareForCall({}, args[1]);
'''
    new = '''template<std::size_t bitsize>
void CallbackOnlyEmitExclusiveReadMemory(oaknut::CodeGenerator& code, EmitContext& ctx, IR::Inst* inst) {
    auto args = ctx.reg_alloc.GetArgumentInfo(inst);
    ASSERT(args[0].IsImmediate());
    ctx.reg_alloc.PrepareForCall({}, args[1], args[0]);
'''
    text = replace_once(text, old, new, "exclusive-read guest location argument")
    emit_memory.write_text(text, encoding="utf-8")

    # 2) Extend only the diagnostic read hook with the exact guest PC.
    config = root / "src/dynarmic/src/dynarmic/interface/A64/config.h"
    text = config.read_text(encoding="utf-8")
    old = '''    virtual void RecordExclusiveReadProfile(std::int32_t /*profile_index*/,
                                            std::uint32_t /*bitsize*/,
                                            std::uint64_t /*elapsed_ns*/) {}
'''
    new = '''    virtual void RecordExclusiveReadProfile(std::int32_t /*profile_index*/,
                                            std::uint32_t /*bitsize*/,
                                            std::uint64_t /*elapsed_ns*/,
                                            std::uint64_t /*guest_pc*/) {}
'''
    text = replace_once(text, old, new, "A64 exclusive-read PC hook")
    config.write_text(text, encoding="utf-8")

    # 3) Decode arg0's A64 LocationDescriptor in the existing exclusive-read trampoline.
    address_space = root / "src/dynarmic/src/dynarmic/backend/arm64/a64_address_space.cpp"
    text = address_space.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr) -> T {
        const auto run_exclusive_read = [&]() -> T {
''',
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr,
                     u64 location_descriptor) -> T {
        const auto run_exclusive_read = [&]() -> T {
''',
        "generic exclusive-read trampoline PC argument",
    )
    text = replace_once(
        text,
        '''        conf.callbacks->RecordExclusiveReadProfile(
            profile_index, static_cast<std::uint32_t>(sizeof(T) * 8), elapsed_ns);
''',
        '''        const u64 guest_pc =
            A64::LocationDescriptor{IR::LocationDescriptor{location_descriptor}}.PC();
        conf.callbacks->RecordExclusiveReadProfile(
            profile_index, static_cast<std::uint32_t>(sizeof(T) * 8), elapsed_ns, guest_pc);
''',
        "generic exclusive-read PC record",
    )
    text = replace_once(
        text,
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr) -> Vector {
        const auto run_exclusive_read = [&]() -> Vector {
''',
        '''    auto fn = [](const A64::UserConfig& conf, A64::VAddr vaddr,
                     u64 location_descriptor) -> Vector {
        const auto run_exclusive_read = [&]() -> Vector {
''',
        "128-bit exclusive-read trampoline PC argument",
    )
    text = replace_once(
        text,
        '''        conf.callbacks->RecordExclusiveReadProfile(profile_index, 128, elapsed_ns);
''',
        '''        const u64 guest_pc =
            A64::LocationDescriptor{IR::LocationDescriptor{location_descriptor}}.PC();
        conf.callbacks->RecordExclusiveReadProfile(profile_index, 128, elapsed_ns, guest_pc);
''',
        "128-bit exclusive-read PC record",
    )
    address_space.write_text(text, encoding="utf-8")

    # 4) Sample only 32-bit LDXR sites after the exact total read timing has already been recorded.
    arm_h = root / "src/core/arm/dynarmic/arm_dynarmic_64.h"
    text = arm_h.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    void RecordExclusiveReadProfile(std::int32_t profile_index, std::uint32_t bitsize,
                                    std::uint64_t elapsed_ns) override;
''',
        '''    void RecordExclusiveReadProfile(std::int32_t profile_index, std::uint32_t bitsize,
                                    std::uint64_t elapsed_ns, std::uint64_t guest_pc) override;
''',
        "DynarmicCallbacks64 exclusive-read PC declaration",
    )
    text = replace_once(
        text,
        '''    s32 m_x1_exclusive_producer_index{-1};
    static constexpr u64 MinimumRunCycles = 10000U;
''',
        '''    s32 m_x1_exclusive_producer_index{-1};
    u32 m_x1_exclusive_pc_sample_state{0x9e3779b9U};
    static constexpr u64 MinimumRunCycles = 10000U;
''',
        "DynarmicCallbacks64 exclusive PC sample state",
    )
    arm_h.write_text(text, encoding="utf-8")

    arm_cpp = root / "src/core/arm/dynarmic/arm_dynarmic_64.cpp"
    text = arm_cpp.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_arm64_exclusive_profiler.h"\n',
        '#include "core/x1_arm64_exclusive_profiler.h"\n'
        '#include "core/x1_arm64_exclusive_pc_profiler.h"\n',
        "ARM64 exclusive PC profiler include",
    )
    old = '''void DynarmicCallbacks64::RecordExclusiveReadProfile(std::int32_t profile_index,
                                                      std::uint32_t bitsize,
                                                      std::uint64_t elapsed_ns) {
    if (profile_index < 0) {
        return;
    }
    X1Arm64ExclusiveProfiler::Get().RecordRead(static_cast<u32>(profile_index), bitsize,
                                               elapsed_ns);
}
'''
    new = '''void DynarmicCallbacks64::RecordExclusiveReadProfile(std::int32_t profile_index,
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
    text = replace_once(text, old, new, "DynarmicCallbacks64 exclusive-read PC implementation")
    arm_cpp.write_text(text, encoding="utf-8")

    # 5) Reuse the same Qualcomm gate and 120-frame report boundary; no behavior changes.
    rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
    text = rasterizer.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '#include "core/x1_arm64_exclusive_profiler.h"\n',
        '#include "core/x1_arm64_exclusive_profiler.h"\n'
        '#include "core/x1_arm64_exclusive_pc_profiler.h"\n',
        "exclusive PC rasterizer include",
    )
    text = replace_once(
        text,
        '''    Core::X1Arm64ExclusiveProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
''',
        '''    Core::X1Arm64ExclusiveProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
    Core::X1Arm64ExclusivePcProfiler::Get().Initialize(
        device.GetDriverID() == VK_DRIVER_ID_QUALCOMM_PROPRIETARY);
''',
        "exclusive PC profiler initialization",
    )
    text = replace_once(
        text,
        '''    Core::X1Arm64ExclusiveProfiler::Get().FrameEnd();
''',
        '''    Core::X1Arm64ExclusiveProfiler::Get().FrameEnd();
    Core::X1Arm64ExclusivePcProfiler::Get().FrameEnd();
''',
        "exclusive PC profiler frame boundary",
    )
    rasterizer.write_text(text, encoding="utf-8")

    # Final observation-only shape checks.
    if emit_memory.read_text(encoding="utf-8").count("PrepareForCall({}, args[1], args[0])") != 1:
        raise RuntimeError("exclusive-read PC argument shape mismatch")
    final_address = address_space.read_text(encoding="utf-8")
    if final_address.count("location_descriptor) -> T") != 1:
        raise RuntimeError("generic exclusive-read PC trampoline mismatch")
    if final_address.count("location_descriptor) -> Vector") != 1:
        raise RuntimeError("128-bit exclusive-read PC trampoline mismatch")
    final_arm = arm_cpp.read_text(encoding="utf-8")
    if final_arm.count("RecordReadSample") != 1:
        raise RuntimeError("exclusive PC sample record count mismatch")
    if final_arm.count("X1Arm64ExclusiveProfiler::Get().RecordRead") != 1:
        raise RuntimeError("existing exact read timing path changed")
    if not pc_profiler_target.exists():
        raise RuntimeError("exclusive PC profiler header was not copied")

    print("Transplanted exact dc95 ARM64 exclusive guest-PC attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
