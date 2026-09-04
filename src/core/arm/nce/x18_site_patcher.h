// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <map>
#include <span>
#include <vector>

#include "common/common_types.h"
#include "core/hle/kernel/code_set.h"
#include "core/hle/kernel/k_typed_address.h"

namespace Core::NCE {

struct X18FallbackSite {
    u32 text_word_index{};
    u32 instruction{};
};

using X18FallbackSiteMap = std::map<u64, u32>;

class X18SitePatcher {
public:
    static constexpr u32 BreakpointImmediate = 0xF000u;
    static constexpr u32 BreakpointInstruction =
        0xD4200000u | (BreakpointImmediate << 5);

    [[nodiscard]] static std::vector<X18FallbackSite> Collect(
        std::span<const u8> program_image, const Kernel::CodeSet::Segment& code);

    static void Apply(Common::ProcessAddress load_base, const Kernel::CodeSet::Segment& code,
                      std::vector<u8>& program_image, std::span<const X18FallbackSite> sites,
                      X18FallbackSiteMap& out_sites);
};

static_assert(X18SitePatcher::BreakpointInstruction == 0xD43E0000u);

} // namespace Core::NCE
