// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/x18_fallback.h"

#include "core/arm/nce/instructions.h"

#include "dynarmic/common/fp/fpcr.h"
#include "dynarmic/frontend/A64/a64_location_descriptor.h"
#include "dynarmic/frontend/A64/a64_types.h"
#include "dynarmic/frontend/A64/translate/a64_translate.h"
#include "dynarmic/ir/basic_block.h"
#include "dynarmic/ir/microinstruction.h"
#include "dynarmic/ir/opcodes.h"

namespace Core::NCE {

namespace {

constexpr u32 RegisterMask = 0x1Fu;
constexpr u32 X18 = 18;

[[nodiscard]] u32 GetRs(u32 instruction) {
    return (instruction >> 16) & RegisterMask;
}

[[nodiscard]] u32 GetRn(u32 instruction) {
    return (instruction >> 5) & RegisterMask;
}

[[nodiscard]] u32 GetRt(u32 instruction) {
    return instruction & RegisterMask;
}

[[nodiscard]] bool IsX18(u32 reg) {
    return reg == X18;
}

[[nodiscard]] bool PairTouchesX18(u32 first_reg) {
    return first_reg == X18 || first_reg + 1 == X18;
}

[[nodiscard]] bool KnownDecoderDisabledAtomicTouchesX18(u32 instruction) {
    // These masks come directly from the decoder-disabled ARMv8.1 patterns in tools/gendynarm.cpp.
    // Keep this list bounded to the families explicitly deferred to IMP-007.
    const bool casp = (instruction & 0xBFA07C00u) == 0x08207C00u;
    if (casp) {
        return IsX18(GetRn(instruction)) || PairTouchesX18(GetRs(instruction)) ||
               PairTouchesX18(GetRt(instruction));
    }

    const bool scalar_cas =
        (instruction & 0xFFA07C00u) == 0x08A07C00u ||
        (instruction & 0xFFA07C00u) == 0x48A07C00u ||
        (instruction & 0xBFA07C00u) == 0x88A07C00u;
    if (scalar_cas) {
        return IsX18(GetRs(instruction)) || IsX18(GetRn(instruction)) ||
               IsX18(GetRt(instruction));
    }

    const bool atomic_memory_group =
        (instruction & 0xFF200000u) == 0x38200000u ||
        (instruction & 0xFF200000u) == 0x78200000u ||
        (instruction & 0xBF200000u) == 0xB8200000u;
    if (!atomic_memory_group) {
        return false;
    }

    const u32 operation = (instruction >> 10) & 0x3Fu;
    const bool deferred_operation = operation <= 0x20u && (operation & 0x3u) == 0;
    if (!deferred_operation) {
        return false;
    }

    return IsX18(GetRs(instruction)) || IsX18(GetRn(instruction)) ||
           IsX18(GetRt(instruction));
}

[[nodiscard]] bool IsX18RegisterReference(const Dynarmic::IR::Inst& inst) {
    using Dynarmic::IR::Opcode;

    switch (inst.GetOpcode()) {
    case Opcode::A64GetW:
    case Opcode::A64GetX:
    case Opcode::A64SetW:
    case Opcode::A64SetX:
        return inst.GetArg(0).GetA64RegRef() == Dynarmic::A64::Reg::R18;
    default:
        return false;
    }
}

} // namespace

X18InstructionClass X18Fallback::ClassifyInstruction(u32 instruction) {
    if (KnownDecoderDisabledAtomicTouchesX18(instruction)) {
        return X18InstructionClass::ExcludedUnsupportedAtomic;
    }

    const Dynarmic::A64::LocationDescriptor descriptor{0, Dynarmic::FP::FPCR{0}, true};
    Dynarmic::IR::Block block{static_cast<Dynarmic::IR::LocationDescriptor>(descriptor)};

    // TranslateSingleInstruction returns the translator's should_continue result, not a pure
    // decode-success flag. Valid terminal instructions such as BR therefore return false while
    // still emitting IR. Inspect the emitted IR before using that boolean as a conservative
    // unsupported signal.
    const bool should_continue =
        Dynarmic::A64::TranslateSingleInstruction(block, descriptor, instruction);

    bool touches_x18 = false;
    for (const auto& inst : block.Instructions()) {
        touches_x18 |= IsX18RegisterReference(inst);
    }

    if (touches_x18) {
        if (Exclusive{instruction}.Verify()) {
            return X18InstructionClass::ExcludedExclusive;
        }
        return X18InstructionClass::SupportedOrdinary;
    }

    if (!should_continue) {
        return X18InstructionClass::Unsupported;
    }

    return X18InstructionClass::NoX18;
}

} // namespace Core::NCE
