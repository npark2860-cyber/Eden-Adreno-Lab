#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <vector>

#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/instructions.h"
#include "core/arm/nce/patcher.h"

using Core::GuestContext;
using Core::NCE::CurrentNceContext;
using Core::NCE::EntryTrampolines;
using Core::NCE::MRS;
using Core::NCE::MSR;
using Core::NCE::Patcher;

extern "C" void* GetCurrentNceContextForGeneratedCode() noexcept {
    return CurrentNceContext::Get();
}

namespace {

constexpr std::size_t EntryOffset = 0x24;
constexpr std::size_t ImageSize = 0x100;

constexpr std::uint32_t Ret = 0xD65F03C0u;
constexpr std::uint32_t MrsX0Tpidr = 0xD53BD040u;    // MRS X0, TPIDR_EL0
constexpr std::uint32_t MrsX18Tpidr = 0xD53BD052u;   // MRS X18, TPIDR_EL0
constexpr std::uint32_t MrsX0Tpidrro = 0xD53BD060u;  // MRS X0, TPIDRRO_EL0
constexpr std::uint32_t MsrTpidrX0 = 0xD51BD040u;    // MSR TPIDR_EL0, X0
constexpr std::uint32_t MsrTpidrX18 = 0xD51BD052u;   // MSR TPIDR_EL0, X18

static_assert(MRS{MrsX0Tpidr}.Verify());
static_assert(MRS{MrsX18Tpidr}.Verify());
static_assert(MRS{MrsX0Tpidrro}.Verify());
static_assert(MSR{MsrTpidrX0}.Verify());
static_assert(MSR{MsrTpidrX18}.Verify());

struct ExecutableImage {
    void* base{};
    bool entry_was_patched{};

    ExecutableImage() = default;
    ExecutableImage(const ExecutableImage&) = delete;
    ExecutableImage& operator=(const ExecutableImage&) = delete;

    ExecutableImage(ExecutableImage&& other) noexcept
        : base(other.base), entry_was_patched(other.entry_was_patched) {
        other.base = nullptr;
    }

    ~ExecutableImage() {
        if (base) {
            VirtualFree(base, 0, MEM_RELEASE);
        }
    }

    explicit operator bool() const noexcept {
        return base != nullptr && entry_was_patched;
    }

    template <typename Fn>
    Fn Entry() const noexcept {
        return reinterpret_cast<Fn>(static_cast<std::uint8_t*>(base) + EntryOffset);
    }
};

ExecutableImage BuildPatched(std::uint32_t first_instruction,
                             std::initializer_list<std::uint32_t> tail = {Ret}) {
    std::vector<std::uint8_t> image(ImageSize, 0);
    auto* words = reinterpret_cast<std::uint32_t*>(image.data());
    std::size_t index = EntryOffset / sizeof(std::uint32_t);
    words[index++] = first_instruction;
    for (const auto instruction : tail) {
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

    const auto patched_entry =
        *reinterpret_cast<const std::uint32_t*>(image.data() + EntryOffset);
    if (patched_entry == first_instruction) {
        // Never execute a raw TPIDR_EL0 access on Windows if the expected patch did not happen.
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
    result.entry_was_patched = true;
    return result;
}

std::uint64_t ReadPhysicalX18() {
    std::uint64_t value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

bool ProbeMrsTpidr(CurrentNceContext::Parameters& params) {
    auto image = BuildPatched(MrsX0Tpidr);
    if (!image) {
        return false;
    }
    const auto entry = image.Entry<std::uint64_t (*)()>();
    return entry() == params.tpidr_el0;
}

bool ProbeMrsTpidrro(CurrentNceContext::Parameters& params) {
    auto image = BuildPatched(MrsX0Tpidrro);
    if (!image) {
        return false;
    }
    const auto entry = image.Entry<std::uint64_t (*)()>();
    return entry() == params.tpidrro_el0;
}

bool ProbeMrsVirtualX18(CurrentNceContext::Parameters& params, GuestContext& guest) {
    auto image = BuildPatched(MrsX18Tpidr);
    if (!image) {
        return false;
    }
    guest.cpu_registers[18] = 0;
    const auto entry = image.Entry<void (*)()>();
    entry();
    return guest.cpu_registers[18] == params.tpidr_el0;
}

bool ProbeMsrFromX0(CurrentNceContext::Parameters& params) {
    auto image = BuildPatched(MsrTpidrX0);
    if (!image) {
        return false;
    }
    constexpr std::uint64_t value = 0xAABBCCDDEEFF1020ull;
    const auto entry = image.Entry<void (*)(std::uint64_t)>();
    entry(value);
    return params.tpidr_el0 == value;
}

bool ProbeMsrFromVirtualX18(CurrentNceContext::Parameters& params, GuestContext& guest) {
    auto image = BuildPatched(MsrTpidrX18);
    if (!image) {
        return false;
    }
    constexpr std::uint64_t value = 0x1828183818481858ull;
    guest.cpu_registers[18] = value;
    params.tpidr_el0 = 0;
    const auto entry = image.Entry<void (*)()>();
    entry();
    return params.tpidr_el0 == value;
}

void Report(const char* name, bool pass) {
    std::printf("%s=%s\n", name, pass ? "PASS" : "FAIL");
}

} // namespace

int main() {
    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    const bool x18_before = ReadPhysicalX18() == teb;

    GuestContext guest{};
    CurrentNceContext::Parameters params{};
    params.native_context = &guest;
    params.tpidr_el0 = 0x1122334455667788ull;
    params.tpidrro_el0 = 0x8877665544332211ull;
    CurrentNceContext::Install(&params);

    const bool mrs_tpidr = ProbeMrsTpidr(params);
    const bool mrs_tpidrro = ProbeMrsTpidrro(params);
    const bool mrs_x18 = ProbeMrsVirtualX18(params, guest);
    const bool msr_x0 = ProbeMsrFromX0(params);
    const bool msr_x18 = ProbeMsrFromVirtualX18(params, guest);

    CurrentNceContext::Clear();
    const bool x18_after = ReadPhysicalX18() == teb;

    Report("IMP008A_MRS_TPIDR", mrs_tpidr);
    Report("IMP008A_MRS_TPIDRRO", mrs_tpidrro);
    Report("IMP008A_MRS_VIRTUAL_X18", mrs_x18);
    Report("IMP008A_MSR_FROM_X0", msr_x0);
    Report("IMP008A_MSR_FROM_VIRTUAL_X18", msr_x18);
    Report("IMP008A_PHYSICAL_X18_TEB_BEFORE", x18_before);
    Report("IMP008A_PHYSICAL_X18_TEB_AFTER", x18_after);

    const bool pass = mrs_tpidr && mrs_tpidrro && mrs_x18 && msr_x0 && msr_x18 &&
                      x18_before && x18_after;
    std::printf("IMP008A_GENERATED_CONTEXT_RUNTIME_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
