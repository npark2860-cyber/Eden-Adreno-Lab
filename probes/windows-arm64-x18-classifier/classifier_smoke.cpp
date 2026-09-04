// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <cstdio>

#include "core/arm/nce/x18_fallback.h"

using Core::NCE::X18Fallback;
using Core::NCE::X18InstructionClass;

namespace {

struct Case {
    const char* name;
    u32 instruction;
    X18InstructionClass expected;
};

constexpr Case Cases[] = {
    {"ADD_READ_X18", 0x8B010240u, X18InstructionClass::SupportedOrdinary},
    {"ADD_WRITE_X18", 0x8B010012u, X18InstructionClass::SupportedOrdinary},
    {"ADD_NO_X18", 0x8B020020u, X18InstructionClass::NoX18},
    {"BR_X18", 0xD61F0240u, X18InstructionClass::SupportedOrdinary},
    {"MRS_X18_TPIDR_EL0", 0xD53BD052u, X18InstructionClass::SupportedOrdinary},
    {"LDXR_X18", 0xC85F7C12u, X18InstructionClass::ExcludedExclusive},
    {"CAS_X18", 0xC8B27C20u, X18InstructionClass::ExcludedUnsupportedAtomic},
    {"CASP_PAIR_TOUCHES_X18", 0x48317C20u,
     X18InstructionClass::ExcludedUnsupportedAtomic},
    {"LDADD_X18", 0xF8320020u, X18InstructionClass::ExcludedUnsupportedAtomic},
    {"SWP_X18", 0xF8328020u, X18InstructionClass::ExcludedUnsupportedAtomic},
};

const char* Name(X18InstructionClass value) {
    switch (value) {
    case X18InstructionClass::NoX18:
        return "NO_X18";
    case X18InstructionClass::SupportedOrdinary:
        return "SUPPORTED_ORDINARY";
    case X18InstructionClass::ExcludedExclusive:
        return "EXCLUDED_EXCLUSIVE";
    case X18InstructionClass::ExcludedUnsupportedAtomic:
        return "EXCLUDED_UNSUPPORTED_ATOMIC";
    case X18InstructionClass::Unsupported:
        return "UNSUPPORTED";
    }
    return "UNKNOWN";
}

} // namespace

int main() {
    bool pass = true;
    for (const auto& test : Cases) {
        const auto actual = X18Fallback::ClassifyInstruction(test.instruction);
        const bool ok = actual == test.expected;
        std::printf("%s=%s actual=%s expected=%s\n", test.name, ok ? "PASS" : "FAIL",
                    Name(actual), Name(test.expected));
        pass &= ok;
    }

    std::printf("X18_CLASSIFIER_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
