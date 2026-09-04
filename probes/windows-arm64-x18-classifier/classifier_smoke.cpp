// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <cstdio>
#include <vector>

#include "core/arm/nce/x18_fallback.h"
#include "core/arm/nce/x18_site_patcher.h"

using Core::NCE::X18Fallback;
using Core::NCE::X18FallbackSiteMap;
using Core::NCE::X18InstructionClass;
using Core::NCE::X18SitePatcher;

namespace {

struct Case {
    const char* name;
    u32 instruction;
    X18InstructionClass expected;
};

constexpr u32 AddReadX18 = 0x8B010240u;
constexpr u32 AddNoX18 = 0x8B020020u;

constexpr Case Cases[] = {
    {"ADD_READ_X18", AddReadX18, X18InstructionClass::SupportedOrdinary},
    {"ADD_WRITE_X18", 0x8B010012u, X18InstructionClass::SupportedOrdinary},
    {"ADD_NO_X18", AddNoX18, X18InstructionClass::NoX18},
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

bool RunSitePatcherSmoke() {
    constexpr u32 HeaderWords = 0x24 / sizeof(u32);
    constexpr u32 X18Word = HeaderWords;
    constexpr u32 PlainWord = HeaderWords + 1;
    constexpr u64 LoadBase = 0x10000000ull;
    constexpr u64 CodeAddress = 0x4000ull;

    std::vector<u8> image(0x80);
    auto* words = reinterpret_cast<u32*>(image.data());
    words[X18Word] = AddReadX18;
    words[PlainWord] = AddNoX18;

    Kernel::CodeSet::Segment code{};
    code.addr = CodeAddress;
    code.offset = 0;
    code.size = static_cast<u32>(image.size());

    const auto sites = X18SitePatcher::Collect(image, code);
    X18FallbackSiteMap runtime_sites;
    X18SitePatcher::Apply(Common::ProcessAddress{LoadBase}, code, image, sites, runtime_sites);

    const u64 expected_pc = LoadBase + CodeAddress + X18Word * sizeof(u32);
    const bool collected = sites.size() == 1 && sites[0].text_word_index == X18Word &&
                           sites[0].instruction == AddReadX18;
    const bool patched = words[X18Word] == X18SitePatcher::BreakpointInstruction &&
                         words[PlainWord] == AddNoX18;
    const auto found = runtime_sites.find(expected_pc);
    const bool mapped = found != runtime_sites.end() && found->second == AddReadX18;

    std::printf("X18_SITE_COLLECT=%s\n", collected ? "PASS" : "FAIL");
    std::printf("X18_SITE_BRK_PATCH=%s\n", patched ? "PASS" : "FAIL");
    std::printf("X18_SITE_RUNTIME_MAP=%s\n", mapped ? "PASS" : "FAIL");
    return collected && patched && mapped;
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

    pass &= RunSitePatcherSmoke();

    std::printf("X18_CLASSIFIER_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
