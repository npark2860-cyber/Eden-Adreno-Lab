// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "core/arm/nce/x18_fallback.h"

#include <cstddef>

#include "core/arm/dynarmic/arm_dynarmic_64.h"
#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/instructions.h"
#include "core/hle/kernel/k_thread.h"

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

void CopyGuestToThreadContext(const GuestContext& guest, Kernel::Svc::ThreadContext& context) {
    for (std::size_t i = 0; i < 29; ++i) {
        context.r[i] = guest.cpu_registers[i];
    }
    context.fp = guest.cpu_registers[29];
    context.lr = guest.cpu_registers[30];
    context.sp = guest.sp;
    context.pc = guest.pc;
    context.pstate = (guest.pstate & ~X18Fallback::NzcvMask) |
                     (guest.nzcv & X18Fallback::NzcvMask);
    context.v = guest.vector_registers;
    context.fpcr = guest.fpcr;
    context.fpsr = guest.fpsr;
    context.tpidr = guest.tpidr_el0;
}

void CopyThreadContextToGuest(const Kernel::Svc::ThreadContext& context, GuestContext& guest) {
    for (std::size_t i = 0; i < 29; ++i) {
        guest.cpu_registers[i] = context.r[i];
    }
    guest.cpu_registers[29] = context.fp;
    guest.cpu_registers[30] = context.lr;
    guest.sp = context.sp;
    guest.pc = context.pc;
    guest.pstate = (guest.pstate & ~X18Fallback::NzcvMask) |
                   (context.pstate & X18Fallback::NzcvMask);
    guest.nzcv = context.pstate & X18Fallback::NzcvMask;
    guest.vector_registers = context.v;
    guest.fpcr = context.fpcr;
    guest.fpsr = context.fpsr;
    guest.tpidr_el0 = context.tpidr;
}

} // namespace

X18InstructionClass X18Fallback::ClassifyInstruction(u32 instruction) {
    if (KnownDecoderDisabledAtomicTouchesX18(instruction)) {
        return X18InstructionClass::ExcludedUnsupportedAtomic;
    }

    if (Exclusive{instruction}.Verify()) {
        return X18InstructionClass::ExcludedExclusive;
    }

    const Dynarmic::A64::LocationDescriptor descriptor{0, Dynarmic::FP::FPCR{0}, true};
    Dynarmic::IR::Block block{static_cast<Dynarmic::IR::LocationDescriptor>(descriptor)};

    if (!Dynarmic::A64::TranslateSingleInstruction(block, descriptor, instruction)) {
        return X18InstructionClass::Unsupported;
    }

    for (const auto& inst : block.Instructions()) {
        if (IsX18RegisterReference(inst)) {
            return X18InstructionClass::SupportedOrdinary;
        }
    }

    return X18InstructionClass::NoX18;
}

X18FallbackStepResult X18Fallback::Step(ArmDynarmic64& backend, Kernel::KThread* thread,
                                        GuestContext& guest) {
    Kernel::Svc::ThreadContext context{};
    CopyGuestToThreadContext(guest, context);

    backend.SetContext(context);
    backend.SetTpidrroEl0(guest.tpidrro_el0);

    const HaltReason step_reason = backend.StepThread(thread);

    backend.GetContext(context);
    CopyThreadContextToGuest(context, guest);

    const u64 raw_reason = static_cast<u64>(step_reason);
    const u64 step_mask = static_cast<u64>(HaltReason::StepThread);

    return {
        .completed = (raw_reason & step_mask) != 0,
        .halt_reason = static_cast<HaltReason>(raw_reason & ~step_mask),
    };
}

} // namespace Core::NCE
