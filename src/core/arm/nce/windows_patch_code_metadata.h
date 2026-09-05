// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#if !defined(_WIN32)
#error windows_patch_code_metadata.h is only available on Windows.
#endif

#include <cstddef>

#include "common/common_types.h"
#include "core/arm/nce/x18_site_patcher.h"

namespace Core::NCE {

// Generated NCE patch code temporarily owns scratch registers and, for some helpers, a guest-stack
// save frame. A cross-thread break must never snapshot that implementation state as architectural
// guest state. Reuse the process-owned tagged metadata map used by IMP-006, but with a distinct
// value magic so normal post-handler lookup and x18 fallback metadata remain disjoint.
class WindowsPatchCodeMetadata {
public:
    static constexpr u64 MetadataKeyBit = 1ull << 63;
    static constexpr u32 MetadataMagic = 0x574E5043u; // "WNPC"

    [[nodiscard]] static constexpr u64 MetadataKey(u64 runtime_start) noexcept {
        return runtime_start | MetadataKeyBit;
    }

    [[nodiscard]] static constexpr u64 MetadataValue(u32 size) noexcept {
        return (static_cast<u64>(MetadataMagic) << 32) | size;
    }

    static void RegisterRange(X18FallbackMetadata& metadata, u64 runtime_start,
                              std::size_t size) noexcept {
        if (size == 0) {
            return;
        }

        // NCE patch sections are bounded by the A64 relative-branch design and therefore fit in
        // the low 32-bit size field by construction.
        metadata[MetadataKey(runtime_start)] = MetadataValue(static_cast<u32>(size));
    }

    [[nodiscard]] static bool Contains(u64 pc, const X18FallbackMetadata& metadata) noexcept {
        for (const auto& [key, value] : metadata) {
            if ((key & MetadataKeyBit) == 0 || static_cast<u32>(value >> 32) != MetadataMagic) {
                continue;
            }

            const u64 start = key & ~MetadataKeyBit;
            const u64 size = static_cast<u32>(value);
            if (pc >= start && pc - start < size) {
                return true;
            }
        }
        return false;
    }
};

static_assert(WindowsPatchCodeMetadata::MetadataMagic != X18SitePatcher::MetadataMagic);

} // namespace Core::NCE
