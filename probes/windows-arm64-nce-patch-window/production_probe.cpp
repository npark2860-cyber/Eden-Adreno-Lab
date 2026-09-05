#include <cstdint>
#include <cstdio>
#include <unordered_map>

#include "core/arm/nce/windows_patch_code_metadata.h"

using Core::NCE::WindowsPatchCodeMetadata;

namespace {

constexpr std::uint64_t X18MetadataKeyBit = 1ull << 63;
constexpr std::uint32_t X18MetadataMagic = 0x58313836u; // "X186"

bool Check(bool condition, const char* marker) {
    std::printf("%s=%s\n", marker, condition ? "PASS" : "FAIL");
    return condition;
}

} // namespace

int main() {
    std::unordered_map<std::uint64_t, std::uint64_t> metadata;

    constexpr std::uint64_t OrdinaryGuestPc = 0x0000000012345000ull;
    constexpr std::uint64_t OrdinaryTrampoline = 0x0000000076543000ull;
    metadata.emplace(OrdinaryGuestPc, OrdinaryTrampoline);

    constexpr std::uint64_t X18GuestPc = 0x0000000011112000ull;
    constexpr std::uint32_t X18Instruction = 0xAA1203E0u;
    metadata.emplace(X18GuestPc | X18MetadataKeyBit,
                     (static_cast<std::uint64_t>(X18MetadataMagic) << 32) | X18Instruction);

    constexpr std::uint64_t PatchStart = 0x0000000040000000ull;
    constexpr std::size_t PatchSize = 0x1000;
    constexpr std::uint64_t PrePatchStart = 0x0000000030000000ull;
    constexpr std::size_t PrePatchSize = 0x800;

    WindowsPatchCodeMetadata::RegisterRange(metadata, PatchStart, PatchSize);
    WindowsPatchCodeMetadata::RegisterRange(metadata, PrePatchStart, PrePatchSize);
    const auto size_before_zero = metadata.size();
    WindowsPatchCodeMetadata::RegisterRange(metadata, 0x50000000ull, 0);

    bool pass = true;
    pass &= Check(metadata.size() == size_before_zero,
                  "IMP008A_PATCH_METADATA_ZERO_RANGE_IGNORED");
    pass &= Check(metadata.at(OrdinaryGuestPc) == OrdinaryTrampoline,
                  "IMP008A_PATCH_METADATA_ORDINARY_POST_HANDLER_PRESERVED");
    pass &= Check(!WindowsPatchCodeMetadata::Contains(OrdinaryGuestPc, metadata),
                  "IMP008A_PATCH_METADATA_ORDINARY_PC_NOT_TAGGED");
    pass &= Check(!WindowsPatchCodeMetadata::Contains(X18GuestPc, metadata),
                  "IMP008A_PATCH_METADATA_X18_TAG_DISJOINT");

    pass &= Check(WindowsPatchCodeMetadata::Contains(PatchStart, metadata),
                  "IMP008A_PATCH_METADATA_POST_START");
    pass &= Check(WindowsPatchCodeMetadata::Contains(PatchStart + 0x400, metadata),
                  "IMP008A_PATCH_METADATA_POST_MIDDLE");
    pass &= Check(WindowsPatchCodeMetadata::Contains(PatchStart + PatchSize - 4, metadata),
                  "IMP008A_PATCH_METADATA_POST_LAST_INSTRUCTION");
    pass &= Check(!WindowsPatchCodeMetadata::Contains(PatchStart - 4, metadata),
                  "IMP008A_PATCH_METADATA_POST_BELOW");
    pass &= Check(!WindowsPatchCodeMetadata::Contains(PatchStart + PatchSize, metadata),
                  "IMP008A_PATCH_METADATA_POST_END_EXCLUSIVE");

    pass &= Check(WindowsPatchCodeMetadata::Contains(PrePatchStart, metadata),
                  "IMP008A_PATCH_METADATA_PRE_START");
    pass &= Check(WindowsPatchCodeMetadata::Contains(PrePatchStart + PrePatchSize - 4, metadata),
                  "IMP008A_PATCH_METADATA_PRE_LAST_INSTRUCTION");
    pass &= Check(!WindowsPatchCodeMetadata::Contains(PrePatchStart + PrePatchSize, metadata),
                  "IMP008A_PATCH_METADATA_PRE_END_EXCLUSIVE");

    const auto tagged_key = WindowsPatchCodeMetadata::MetadataKey(PatchStart);
    const auto tagged_value = metadata.at(tagged_key);
    pass &= Check((tagged_key & WindowsPatchCodeMetadata::MetadataKeyBit) != 0,
                  "IMP008A_PATCH_METADATA_KEY_TAGGED");
    pass &= Check(static_cast<std::uint32_t>(tagged_value >> 32) ==
                      WindowsPatchCodeMetadata::MetadataMagic,
                  "IMP008A_PATCH_METADATA_MAGIC");
    pass &= Check(static_cast<std::uint32_t>(tagged_value) == PatchSize,
                  "IMP008A_PATCH_METADATA_SIZE");

    std::printf("IMP008A_WINDOWS_PATCH_WINDOW_METADATA_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 20;
}
