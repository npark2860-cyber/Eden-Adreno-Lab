#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <optional>
#include <vector>

#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/patcher.h"

using Core::GuestContext;
using Core::NCE::CurrentNceContext;
using Core::NCE::EntryTrampolines;
using Core::NCE::Patcher;

extern "C" void* GetCurrentNceContextForGeneratedCode() noexcept {
    return CurrentNceContext::Get();
}

namespace {

constexpr std::size_t EntryOffset = 0x24;
constexpr std::size_t ImageSize = 0x200;
constexpr std::uint64_t InitialValue = 0x1122334455667788ull;
constexpr std::uint64_t SecondValue = 0x2233445566778899ull;
constexpr std::uint64_t StoreValue = 0x8877665544332211ull;
constexpr std::uint64_t StoreSecondValue = 0x7766554433221100ull;
constexpr std::uint64_t AddValue = 0x31ull;

constexpr std::uint32_t Ret = 0xD65F03C0u;
constexpr std::uint32_t MovX5X19 = 0xAA1303E5u;
constexpr std::uint32_t MovX19X1 = 0xAA0103F3u;
constexpr std::uint32_t MovX19X4 = 0xAA0403F3u;
constexpr std::uint32_t MovX0X19 = 0xAA1303E0u;
constexpr std::uint32_t MovX19X5 = 0xAA0503F3u;
constexpr std::uint32_t MovX0X2 = 0xAA0203E0u;
constexpr std::uint32_t MovX0X1 = 0xAA0103E0u;

constexpr std::uint32_t CasX18X1AtX0 = 0xC8B27C01u;
constexpr std::uint32_t CasX1X18AtX0 = 0xC8A17C12u;
constexpr std::uint32_t CasX0X1AtX18 = 0xC8A07E41u;
constexpr std::uint32_t CasalX18X1AtX0 = 0xC8F2FC01u;
constexpr std::uint32_t CaspX18X19X2X3AtX0 = 0x48327C02u;
constexpr std::uint32_t CaspX2X3X18X19AtX0 = 0x48227C12u;
constexpr std::uint32_t CaspX0X1X2X3AtX4 = 0x48207C82u;
constexpr std::uint32_t LdaddX18X1AtX0 = 0xF8320001u;
constexpr std::uint32_t LdaddX1X18AtX0 = 0xF8210012u;
constexpr std::uint32_t SwpX18X1AtX0 = 0xF8328001u;
constexpr std::uint32_t SwpX1X18AtX0 = 0xF8218012u;
constexpr std::uint32_t LdaddalX18X1AtX0 = 0xF8F20001u;

struct PairValue {
    std::uint64_t first;
    std::uint64_t second;
};

struct ExecutableImage {
    void* base{};

    ExecutableImage() = default;
    ExecutableImage(const ExecutableImage&) = delete;
    ExecutableImage& operator=(const ExecutableImage&) = delete;

    ExecutableImage(ExecutableImage&& other) noexcept : base(other.base) {
        other.base = nullptr;
    }

    ExecutableImage& operator=(ExecutableImage&& other) noexcept {
        if (this != &other) {
            if (base) {
                VirtualFree(base, 0, MEM_RELEASE);
            }
            base = other.base;
            other.base = nullptr;
        }
        return *this;
    }

    ~ExecutableImage() {
        if (base) {
            VirtualFree(base, 0, MEM_RELEASE);
        }
    }

    explicit operator bool() const noexcept {
        return base != nullptr;
    }

    template <typename Fn>
    Fn Entry() const noexcept {
        return reinterpret_cast<Fn>(static_cast<std::uint8_t*>(base) + EntryOffset);
    }
};

std::optional<std::vector<std::uint8_t>> PatchProgram(
    std::initializer_list<std::uint32_t> body) {
    std::vector<std::uint8_t> image(ImageSize, 0);
    auto* words = reinterpret_cast<std::uint32_t*>(image.data());
    std::size_t index = EntryOffset / sizeof(std::uint32_t);
    for (const auto instruction : body) {
        words[index++] = instruction;
    }

    Kernel::CodeSet::Segment code{};
    code.offset = 0;
    code.addr = Common::ProcessAddress{0};
    code.size = static_cast<std::uint32_t>(ImageSize);

    Patcher patcher;
    if (!patcher.PatchText(image, code)) {
        return std::nullopt;
    }

    EntryTrampolines trampolines;
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{0}, code, image, &trampolines)) {
        return std::nullopt;
    }
    return image;
}

ExecutableImage BuildPatched(std::initializer_list<std::uint32_t> body) {
    auto image = PatchProgram(body);
    if (!image) {
        return {};
    }

    void* memory = VirtualAlloc(nullptr, image->size(), MEM_COMMIT | MEM_RESERVE,
                                PAGE_EXECUTE_READWRITE);
    if (!memory) {
        return {};
    }

    std::memcpy(memory, image->data(), image->size());
    if (!FlushInstructionCache(GetCurrentProcess(), memory, image->size())) {
        VirtualFree(memory, 0, MEM_RELEASE);
        return {};
    }

    ExecutableImage result;
    result.base = memory;
    return result;
}

std::uint64_t ReadPhysicalX18() {
    std::uint64_t value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

void Report(const char* name, bool pass) {
    std::printf("%s=%s\n", name, pass ? "PASS" : "FAIL");
}

bool ProbeNonX18CaspEncodingPreserved() {
    auto image = PatchProgram({CaspX0X1X2X3AtX4, Ret});
    if (!image) {
        return false;
    }
    const auto* words = reinterpret_cast<const std::uint32_t*>(image->data());
    return words[EntryOffset / sizeof(std::uint32_t)] == CaspX0X1X2X3AtX4;
}

bool ProbeCasExpectedSuccessFailure(GuestContext& guest) {
    auto image = BuildPatched({CasX18X1AtX0, Ret});
    if (!image) {
        return false;
    }

    const auto entry = image.Entry<void (*)(std::uint64_t*, std::uint64_t)>();
    alignas(64) std::uint64_t target = InitialValue;

    guest.cpu_registers[18] = InitialValue;
    entry(&target, StoreValue);
    const bool success = target == StoreValue && guest.cpu_registers[18] == InitialValue;

    target = InitialValue;
    guest.cpu_registers[18] = SecondValue;
    entry(&target, StoreValue);
    const bool failure = target == InitialValue && guest.cpu_registers[18] == InitialValue;
    return success && failure;
}

bool ProbeCasReplacementRole(GuestContext& guest) {
    auto image = BuildPatched({CasX1X18AtX0, MovX0X1, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = StoreValue;
    const auto entry = image.Entry<std::uint64_t (*)(std::uint64_t*, std::uint64_t)>();
    const auto old = entry(&target, InitialValue);
    return old == InitialValue && target == StoreValue && guest.cpu_registers[18] == StoreValue;
}

bool ProbeCasBaseRole(GuestContext& guest) {
    auto image = BuildPatched({CasX0X1AtX18, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = reinterpret_cast<std::uint64_t>(&target);
    const auto entry = image.Entry<std::uint64_t (*)(std::uint64_t, std::uint64_t)>();
    const auto old = entry(InitialValue, StoreValue);
    return old == InitialValue && target == StoreValue &&
           guest.cpu_registers[18] == reinterpret_cast<std::uint64_t>(&target);
}

bool ProbeCasalAcquireRelease(GuestContext& guest) {
    auto image = BuildPatched({CasalX18X1AtX0, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = InitialValue;
    const auto entry = image.Entry<void (*)(std::uint64_t*, std::uint64_t)>();
    entry(&target, StoreValue);
    return target == StoreValue && guest.cpu_registers[18] == InitialValue;
}

bool ProbeCaspExpectedSuccessFailure(GuestContext& guest) {
    auto image = BuildPatched({MovX5X19, MovX19X1, CaspX18X19X2X3AtX0, MovX0X19,
                               MovX19X5, Ret});
    if (!image) {
        return false;
    }

    using Fn = std::uint64_t (*)(PairValue*, std::uint64_t, std::uint64_t, std::uint64_t);
    const auto entry = image.Entry<Fn>();
    alignas(16) PairValue target{InitialValue, SecondValue};

    guest.cpu_registers[18] = InitialValue;
    const auto old_second = entry(&target, SecondValue, StoreValue, StoreSecondValue);
    const bool success = target.first == StoreValue && target.second == StoreSecondValue &&
                         guest.cpu_registers[18] == InitialValue && old_second == SecondValue;

    target = {InitialValue, SecondValue};
    guest.cpu_registers[18] = StoreValue;
    const auto failed_old_second = entry(&target, SecondValue, StoreValue, StoreSecondValue);
    const bool failure = target.first == InitialValue && target.second == SecondValue &&
                         guest.cpu_registers[18] == InitialValue &&
                         failed_old_second == SecondValue;
    return success && failure;
}

bool ProbeCaspReplacementRole(GuestContext& guest) {
    auto image = BuildPatched({MovX5X19, MovX19X4, CaspX2X3X18X19AtX0, MovX0X2,
                               MovX19X5, Ret});
    if (!image) {
        return false;
    }

    using Fn = std::uint64_t (*)(PairValue*, std::uint64_t, std::uint64_t, std::uint64_t,
                                 std::uint64_t);
    const auto entry = image.Entry<Fn>();
    alignas(16) PairValue target{InitialValue, SecondValue};
    guest.cpu_registers[18] = StoreValue;
    const auto old_first = entry(&target, 0, InitialValue, SecondValue, StoreSecondValue);
    return old_first == InitialValue && target.first == StoreValue &&
           target.second == StoreSecondValue && guest.cpu_registers[18] == StoreValue;
}

bool ProbeLdaddSourceRole(GuestContext& guest) {
    auto image = BuildPatched({LdaddX18X1AtX0, MovX0X1, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = AddValue;
    const auto entry = image.Entry<std::uint64_t (*)(std::uint64_t*)>();
    const auto old = entry(&target);
    return old == InitialValue && target == InitialValue + AddValue &&
           guest.cpu_registers[18] == AddValue;
}

bool ProbeLdaddResultRole(GuestContext& guest) {
    auto image = BuildPatched({LdaddX1X18AtX0, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = 0;
    const auto entry = image.Entry<void (*)(std::uint64_t*, std::uint64_t)>();
    entry(&target, AddValue);
    return target == InitialValue + AddValue && guest.cpu_registers[18] == InitialValue;
}

bool ProbeSwpSourceRole(GuestContext& guest) {
    auto image = BuildPatched({SwpX18X1AtX0, MovX0X1, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = StoreValue;
    const auto entry = image.Entry<std::uint64_t (*)(std::uint64_t*)>();
    const auto old = entry(&target);
    return old == InitialValue && target == StoreValue && guest.cpu_registers[18] == StoreValue;
}

bool ProbeSwpResultRole(GuestContext& guest) {
    auto image = BuildPatched({SwpX1X18AtX0, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = 0;
    const auto entry = image.Entry<void (*)(std::uint64_t*, std::uint64_t)>();
    entry(&target, StoreValue);
    return target == StoreValue && guest.cpu_registers[18] == InitialValue;
}

bool ProbeLdaddalAcquireRelease(GuestContext& guest) {
    auto image = BuildPatched({LdaddalX18X1AtX0, MovX0X1, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = AddValue;
    const auto entry = image.Entry<std::uint64_t (*)(std::uint64_t*)>();
    const auto old = entry(&target);
    return old == InitialValue && target == InitialValue + AddValue &&
           guest.cpu_registers[18] == AddValue;
}

} // namespace

int main() {
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    const bool x18_before = ReadPhysicalX18() == teb;

    GuestContext guest{};
    CurrentNceContext::Parameters parameters{};
    parameters.native_context = &guest;
    CurrentNceContext::Install(&parameters);

    const bool casp_encoding_ok = ProbeNonX18CaspEncodingPreserved();
    const bool cas_expected_ok = ProbeCasExpectedSuccessFailure(guest);
    const bool cas_replacement_ok = ProbeCasReplacementRole(guest);
    const bool cas_base_ok = ProbeCasBaseRole(guest);
    const bool casal_ok = ProbeCasalAcquireRelease(guest);
    const bool casp_expected_ok = ProbeCaspExpectedSuccessFailure(guest);
    const bool casp_replacement_ok = ProbeCaspReplacementRole(guest);
    const bool ldadd_source_ok = ProbeLdaddSourceRole(guest);
    const bool ldadd_result_ok = ProbeLdaddResultRole(guest);
    const bool swp_source_ok = ProbeSwpSourceRole(guest);
    const bool swp_result_ok = ProbeSwpResultRole(guest);
    const bool ldaddal_ok = ProbeLdaddalAcquireRelease(guest);

    CurrentNceContext::Clear();
    const bool x18_after = ReadPhysicalX18() == teb;

    Report("PRODUCTION_LSE_X18_TEB_BEFORE", x18_before);
    Report("PRODUCTION_LSE_NONX18_CASP_ENCODING_PRESERVED", casp_encoding_ok);
    Report("PRODUCTION_LSE_CAS_X18_EXPECTED_SUCCESS_FAILURE", cas_expected_ok);
    Report("PRODUCTION_LSE_CAS_X18_REPLACEMENT", cas_replacement_ok);
    Report("PRODUCTION_LSE_CAS_X18_BASE", cas_base_ok);
    Report("PRODUCTION_LSE_CASAL_X18_ACQREL", casal_ok);
    Report("PRODUCTION_LSE_CASP_X18_EXPECTED_PAIR_SUCCESS_FAILURE", casp_expected_ok);
    Report("PRODUCTION_LSE_CASP_X18_REPLACEMENT_PAIR", casp_replacement_ok);
    Report("PRODUCTION_LSE_LDADD_X18_SOURCE", ldadd_source_ok);
    Report("PRODUCTION_LSE_LDADD_X18_RESULT", ldadd_result_ok);
    Report("PRODUCTION_LSE_SWP_X18_SOURCE", swp_source_ok);
    Report("PRODUCTION_LSE_SWP_X18_RESULT", swp_result_ok);
    Report("PRODUCTION_LSE_LDADDAL_X18_ACQREL", ldaddal_ok);
    Report("PRODUCTION_LSE_X18_TEB_AFTER", x18_after);

    const bool pass = x18_before && casp_encoding_ok && cas_expected_ok && cas_replacement_ok &&
                      cas_base_ok && casal_ok && casp_expected_ok && casp_replacement_ok &&
                      ldadd_source_ok && ldadd_result_ok && swp_source_ok && swp_result_ok &&
                      ldaddal_ok && x18_after;
    std::printf("IMP007_LSE_PRODUCTION_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
