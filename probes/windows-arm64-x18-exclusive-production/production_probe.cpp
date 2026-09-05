#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
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
constexpr std::size_t ImageSize = 0x100;
constexpr std::uint64_t InitialValue = 0x1122334455667788ull;
constexpr std::uint64_t SecondValue = 0x2233445566778899ull;
constexpr std::uint64_t StoreValue = 0x8877665544332211ull;
constexpr unsigned Attempts = 4096;

constexpr std::uint32_t Ret = 0xD65F03C0u;
constexpr std::uint32_t LdxrX0FromX18 = 0xC85F7E40u;
constexpr std::uint32_t LdxrX18FromX0 = 0xC85F7C12u;
constexpr std::uint32_t LdxrX1FromX0 = 0xC85F7C01u;
constexpr std::uint32_t StxrW2X18ToX0 = 0xC8027C12u;
constexpr std::uint32_t StxrW18X1ToX0 = 0xC8127C01u;
constexpr std::uint32_t AddX1X1One = 0x91000421u;
constexpr std::uint32_t MovW0W2 = 0x2A0203E0u;

constexpr std::uint32_t LdxpX0X1FromX18 = 0xC87F0640u;
constexpr std::uint32_t StxpW3X0X1ToX18 = 0xC8230640u;
constexpr std::uint32_t LdxpX18X1FromX0 = 0xC87F0412u;
constexpr std::uint32_t LdxpX2X3FromX0 = 0xC87F0C02u;
constexpr std::uint32_t StxpW4X18X3ToX0 = 0xC8240C12u;
constexpr std::uint32_t StxpW18X2X3ToX0 = 0xC8320C02u;
constexpr std::uint32_t MovW0W3 = 0x2A0303E0u;
constexpr std::uint32_t MovW0W4 = 0x2A0403E0u;

constexpr std::uint32_t LdaxrX1FromX18 = 0xC85FFE41u;
constexpr std::uint32_t StlxrW2X1ToX18 = 0xC802FE41u;

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

ExecutableImage BuildPatched(std::initializer_list<std::uint32_t> body) {
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
        return {};
    }

    EntryTrampolines trampolines;
    if (!patcher.RelocateAndCopy(Common::ProcessAddress{0}, code, image, &trampolines)) {
        return {};
    }

    void* memory = VirtualAlloc(nullptr, image.size(), MEM_COMMIT | MEM_RESERVE,
                                PAGE_EXECUTE_READWRITE);
    if (!memory) {
        return {};
    }

    std::memcpy(memory, image.data(), image.size());
    if (!FlushInstructionCache(GetCurrentProcess(), memory, image.size())) {
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

bool ProbeBaseRole(GuestContext& guest) {
    auto image = BuildPatched({LdxrX0FromX18, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = reinterpret_cast<std::uint64_t>(&target);
    const auto entry = image.Entry<std::uint64_t (*)()>();
    return entry() == InitialValue && target == InitialValue;
}

bool ProbeResultRole(GuestContext& guest) {
    auto image = BuildPatched({LdxrX18FromX0, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target = InitialValue;
    guest.cpu_registers[18] = 0;
    const auto entry = image.Entry<void (*)(std::uint64_t*)>();
    entry(&target);
    return guest.cpu_registers[18] == InitialValue && target == InitialValue;
}

bool ProbeStoreDataRole(GuestContext& guest) {
    auto image = BuildPatched({LdxrX1FromX0, StxrW2X18ToX0, MovW0W2, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target{};
    guest.cpu_registers[18] = StoreValue;
    const auto entry = image.Entry<std::uint32_t (*)(std::uint64_t*)>();
    for (unsigned i = 0; i < Attempts; ++i) {
        target = InitialValue;
        if (entry(&target) == 0 && target == StoreValue) {
            return true;
        }
    }
    return false;
}

bool ProbeStatusRole(GuestContext& guest) {
    auto image = BuildPatched({LdxrX1FromX0, AddX1X1One, StxrW18X1ToX0, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target{};
    const auto entry = image.Entry<void (*)(std::uint64_t*)>();
    for (unsigned i = 0; i < Attempts; ++i) {
        target = InitialValue;
        guest.cpu_registers[18] = ~0ull;
        entry(&target);
        if (guest.cpu_registers[18] == 0 && target == InitialValue + 1) {
            return true;
        }
    }
    return false;
}

bool ProbePairBaseRole(GuestContext& guest) {
    auto image = BuildPatched({LdxpX0X1FromX18, StxpW3X0X1ToX18, MovW0W3, Ret});
    if (!image) {
        return false;
    }

    alignas(16) PairValue target{};
    guest.cpu_registers[18] = reinterpret_cast<std::uint64_t>(&target);
    const auto entry = image.Entry<std::uint32_t (*)()>();
    for (unsigned i = 0; i < Attempts; ++i) {
        target = {InitialValue, SecondValue};
        if (entry() == 0 && target.first == InitialValue && target.second == SecondValue) {
            return true;
        }
    }
    return false;
}

bool ProbePairResultRole(GuestContext& guest) {
    auto image = BuildPatched({LdxpX18X1FromX0, Ret});
    if (!image) {
        return false;
    }

    alignas(16) PairValue target{InitialValue, SecondValue};
    guest.cpu_registers[18] = 0;
    const auto entry = image.Entry<void (*)(PairValue*)>();
    entry(&target);
    return guest.cpu_registers[18] == InitialValue;
}

bool ProbePairStoreDataRole(GuestContext& guest) {
    auto image = BuildPatched({LdxpX2X3FromX0, StxpW4X18X3ToX0, MovW0W4, Ret});
    if (!image) {
        return false;
    }

    alignas(16) PairValue target{};
    guest.cpu_registers[18] = StoreValue;
    const auto entry = image.Entry<std::uint32_t (*)(PairValue*)>();
    for (unsigned i = 0; i < Attempts; ++i) {
        target = {InitialValue, SecondValue};
        if (entry(&target) == 0 && target.first == StoreValue && target.second == SecondValue) {
            return true;
        }
    }
    return false;
}

bool ProbePairStatusRole(GuestContext& guest) {
    auto image = BuildPatched({LdxpX2X3FromX0, StxpW18X2X3ToX0, Ret});
    if (!image) {
        return false;
    }

    alignas(16) PairValue target{};
    const auto entry = image.Entry<void (*)(PairValue*)>();
    for (unsigned i = 0; i < Attempts; ++i) {
        target = {InitialValue, SecondValue};
        guest.cpu_registers[18] = ~0ull;
        entry(&target);
        if (guest.cpu_registers[18] == 0 && target.first == InitialValue &&
            target.second == SecondValue) {
            return true;
        }
    }
    return false;
}

bool ProbeAcquireRelease(GuestContext& guest) {
    auto image = BuildPatched({LdaxrX1FromX18, AddX1X1One, StlxrW2X1ToX18, MovW0W2, Ret});
    if (!image) {
        return false;
    }

    alignas(64) std::uint64_t target{};
    guest.cpu_registers[18] = reinterpret_cast<std::uint64_t>(&target);
    const auto entry = image.Entry<std::uint32_t (*)()>();
    for (unsigned i = 0; i < Attempts; ++i) {
        target = InitialValue;
        if (entry() == 0 && target == InitialValue + 1) {
            return true;
        }
    }
    return false;
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

    const bool base_ok = ProbeBaseRole(guest);
    const bool result_ok = ProbeResultRole(guest);
    const bool store_data_ok = ProbeStoreDataRole(guest);
    const bool status_ok = ProbeStatusRole(guest);
    const bool pair_base_ok = ProbePairBaseRole(guest);
    const bool pair_result_ok = ProbePairResultRole(guest);
    const bool pair_store_data_ok = ProbePairStoreDataRole(guest);
    const bool pair_status_ok = ProbePairStatusRole(guest);
    const bool acquire_release_ok = ProbeAcquireRelease(guest);

    CurrentNceContext::Clear();
    const bool x18_after = ReadPhysicalX18() == teb;

    Report("PRODUCTION_X18_TEB_BEFORE", x18_before);
    Report("PRODUCTION_SCALAR_X18_BASE", base_ok);
    Report("PRODUCTION_SCALAR_X18_RESULT", result_ok);
    Report("PRODUCTION_SCALAR_X18_STORE_DATA", store_data_ok);
    Report("PRODUCTION_SCALAR_X18_STATUS", status_ok);
    Report("PRODUCTION_PAIR_X18_BASE", pair_base_ok);
    Report("PRODUCTION_PAIR_X18_RESULT", pair_result_ok);
    Report("PRODUCTION_PAIR_X18_STORE_DATA", pair_store_data_ok);
    Report("PRODUCTION_PAIR_X18_STATUS", pair_status_ok);
    Report("PRODUCTION_ACQUIRE_RELEASE_X18_BASE", acquire_release_ok);
    Report("PRODUCTION_X18_TEB_AFTER", x18_after);

    const bool scalar_pass = base_ok && result_ok && store_data_ok && status_ok;
    const bool pair_pass = pair_base_ok && pair_result_ok && pair_store_data_ok && pair_status_ok;
    const bool pass = x18_before && scalar_pass && pair_pass && acquire_release_ok && x18_after;

    std::printf("IMP007_CLASSIC_EXCLUSIVE_PRODUCTION_SCALAR_SMOKE=%s\n",
                scalar_pass ? "PASS" : "FAIL");
    std::printf("IMP007_CLASSIC_EXCLUSIVE_PRODUCTION_PAIR_SMOKE=%s\n",
                pair_pass ? "PASS" : "FAIL");
    std::printf("IMP007_CLASSIC_EXCLUSIVE_PRODUCTION_ACQREL_SMOKE=%s\n",
                acquire_release_ok ? "PASS" : "FAIL");
    std::printf("IMP007_CLASSIC_EXCLUSIVE_PRODUCTION_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
