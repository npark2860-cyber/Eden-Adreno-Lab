#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include "core/arm/arm_interface.h"
#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/guest_context.h"
#include "core/arm/nce/instructions.h"
#include "core/arm/nce/patcher.h"
#include "core/arm/nce/windows_nce_transition.h"

using Core::GuestContext;
using Core::HaltReason;
using Core::NCE::CurrentNceContext;
using Core::NCE::EntryTrampolines;
using Core::NCE::PatchMode;
using Core::NCE::Patcher;
using Core::NCE::SVC;

namespace {

constexpr std::size_t ImageSize = 0x100;
constexpr std::size_t CodeAllocationSize = 0x20000;
constexpr std::size_t EntryOffset = 0x24;
constexpr std::size_t InitialStubOffset = 0x18000;
constexpr std::size_t GuestStackSize = 0x10000;

constexpr std::uint32_t Svc6 = 0xD40000C1u;
constexpr std::uint32_t Svc7 = 0xD40000E1u;
constexpr std::uint32_t Brk = 0xD4200000u;
constexpr std::uint32_t LockLocked = 0;
constexpr std::uint32_t LockUnlocked = 1;

static_assert(SVC{Svc6}.Verify() && SVC{Svc6}.GetValue() == 6);
static_assert(SVC{Svc7}.Verify() && SVC{Svc7}.GetValue() == 7);
static_assert(offsetof(GuestContext, windows_guest_stack_base) == 0x440);
static_assert(offsetof(GuestContext, windows_guest_stack_limit) == 0x448);
static_assert(offsetof(GuestContext, windows_host_stack_base) == 0x450);
static_assert(offsetof(GuestContext, windows_host_stack_limit) == 0x458);

constexpr std::uint64_t InitialX14 = 0x1414141414141414ull;
constexpr std::uint64_t InitialX15 = 0x1515151515151515ull;
constexpr std::uint64_t InitialX16 = 0x1616161616161616ull;
constexpr std::uint64_t InitialX17 = 0x1717171717171717ull;
constexpr std::uint64_t ResumeX0 = 0xA0A0A0A0A0A0A0A0ull;

std::uint64_t ReadPhysicalX18() {
    std::uint64_t value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
}

std::uint32_t EncodeLdrX(unsigned rt, unsigned rn, unsigned byte_offset) {
    if ((byte_offset & 7u) != 0 || byte_offset / 8u >= 4096u) {
        return 0;
    }
    return 0xF9400000u | ((byte_offset / 8u) << 10) | (rn << 5) | rt;
}

std::uint32_t EncodeStrX(unsigned rt, unsigned rn, unsigned byte_offset) {
    if ((byte_offset & 7u) != 0 || byte_offset / 8u >= 4096u) {
        return 0;
    }
    return 0xF9000000u | ((byte_offset / 8u) << 10) | (rn << 5) | rt;
}

std::uint32_t EncodeB(std::uintptr_t instruction_pc, std::uintptr_t target) {
    const auto delta = static_cast<std::int64_t>(target) - static_cast<std::int64_t>(instruction_pc);
    if ((delta & 3) != 0 || delta < -(128ll << 20) || delta >= (128ll << 20)) {
        return 0;
    }
    return 0x14000000u | (static_cast<std::uint32_t>(delta >> 2) & 0x03FFFFFFu);
}

bool HasSupervisorCall(std::uint64_t value) {
    return (value & static_cast<std::uint64_t>(HaltReason::SupervisorCall)) != 0;
}

void Report(const char* name, bool pass) {
    std::printf("%s=%s\n", name, pass ? "PASS" : "FAIL");
}

struct Allocation {
    std::uint8_t* base{};

    ~Allocation() {
        if (base) {
            VirtualFree(base, 0, MEM_RELEASE);
        }
    }
};

} // namespace

int main() {
#if !defined(_WIN32) || !defined(ARCHITECTURE_arm64) || !defined(HAS_NCE)
    Report("IMP008_D2_PLATFORM_CONTRACT", false);
    return 1;
#else
    auto* const tib = reinterpret_cast<NT_TIB*>(NtCurrentTeb());
    const auto teb_address = reinterpret_cast<std::uint64_t>(tib);
    const auto host_stack_base = reinterpret_cast<std::uint64_t>(tib->StackBase);
    const auto host_stack_limit = reinterpret_cast<std::uint64_t>(tib->StackLimit);
    const bool x18_before = ReadPhysicalX18() == teb_address;

    std::vector<std::uint8_t> image(ImageSize, 0);
    auto* words = reinterpret_cast<std::uint32_t*>(image.data());
    words[EntryOffset / 4] = Svc6;
    words[EntryOffset / 4 + 1] = Svc7;
    words[EntryOffset / 4 + 2] = Brk;

    Kernel::CodeSet::Segment code{};
    code.offset = 0;
    code.addr = Common::ProcessAddress{0};
    code.size = static_cast<std::uint32_t>(ImageSize);

    Patcher patcher;
    const bool patch_ok = patcher.PatchText(image, code);
    const bool mode_ok = patch_ok && patcher.GetPatchMode() == PatchMode::PostData;

    Allocation code_allocation;
    code_allocation.base = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, CodeAllocationSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    Allocation guest_stack;
    guest_stack.base = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, GuestStackSize, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!code_allocation.base || !guest_stack.base || !mode_ok) {
        Report("IMP008_D2_ALLOCATE", false);
        return 1;
    }

    EntryTrampolines trampolines;
    const bool relocate_ok = patcher.RelocateAndCopy(
        Common::ProcessAddress{reinterpret_cast<std::uintptr_t>(code_allocation.base)}, code, image,
        &trampolines);
    if (!relocate_ok || image.size() >= InitialStubOffset) {
        Report("IMP008_D2_RELOCATE", false);
        return 1;
    }
    std::memcpy(code_allocation.base, image.data(), image.size());

    const auto first_svc_pc = reinterpret_cast<std::uintptr_t>(code_allocation.base) + EntryOffset;
    const auto second_svc_pc = first_svc_pc + 4;
    auto* stub_words =
        reinterpret_cast<std::uint32_t*>(code_allocation.base + InitialStubOffset);

    // The raw, unpatched entry stub is the first code after WindowsNceEnterGuest's SP handoff.
    // Physical x18 is therefore the real Windows TEB. Capture the pair without calling host code.
    stub_words[0] = EncodeLdrX(14, 18, 8);
    stub_words[1] = EncodeStrX(14, 17, offsetof(GuestContext, tpidrro_el0));
    stub_words[2] = EncodeLdrX(15, 18, 16);
    stub_words[3] = EncodeStrX(15, 17, offsetof(GuestContext, tpidr_el0));
    stub_words[4] =
        EncodeLdrX(14, 17, offsetof(GuestContext, cpu_registers) + sizeof(std::uint64_t) * 14);
    stub_words[5] =
        EncodeLdrX(15, 17, offsetof(GuestContext, cpu_registers) + sizeof(std::uint64_t) * 15);
    stub_words[6] =
        EncodeLdrX(16, 17, offsetof(GuestContext, cpu_registers) + sizeof(std::uint64_t) * 16);
    stub_words[7] =
        EncodeLdrX(17, 17, offsetof(GuestContext, cpu_registers) + sizeof(std::uint64_t) * 17);
    stub_words[8] =
        EncodeB(reinterpret_cast<std::uintptr_t>(&stub_words[8]), first_svc_pc);

    bool stub_ok = true;
    for (std::size_t i = 0; i < 9; ++i) {
        stub_ok &= stub_words[i] != 0;
    }
    if (!stub_ok ||
        !FlushInstructionCache(GetCurrentProcess(), code_allocation.base, CodeAllocationSize)) {
        Report("IMP008_D2_ENTRY_CAPTURE_STUB", false);
        return 1;
    }

    const auto guest_stack_limit = reinterpret_cast<std::uint64_t>(guest_stack.base);
    const auto guest_stack_base = guest_stack_limit + GuestStackSize;
    const auto guest_stack_top = guest_stack_base & ~std::uint64_t{0xF};

    GuestContext guest{};
    guest.sp = guest_stack_top;
    guest.pc = first_svc_pc;
    guest.cpu_registers[14] = InitialX14;
    guest.cpu_registers[15] = InitialX15;
    guest.cpu_registers[16] = InitialX16;
    guest.cpu_registers[17] = InitialX17;
    guest.windows_guest_stack_base = guest_stack_base;
    guest.windows_guest_stack_limit = guest_stack_limit;
    guest.windows_host_stack_base = host_stack_base;
    guest.windows_host_stack_limit = host_stack_limit;

    CurrentNceContext::Parameters params{};
    params.native_context = &guest;
    params.lock.store(LockUnlocked, std::memory_order_release);
    CurrentNceContext::Install(&params);

    const auto first_result = Core::NCE::WindowsNceEnterGuest(
        &guest, code_allocation.base + InitialStubOffset);

    const bool guest_entry_pair_ok =
        guest.tpidrro_el0 == guest_stack_base && guest.tpidr_el0 == guest_stack_limit;
    const bool first_host_pair_ok =
        reinterpret_cast<std::uint64_t>(tib->StackBase) == host_stack_base &&
        reinterpret_cast<std::uint64_t>(tib->StackLimit) == host_stack_limit;
    const bool first_return_ok = HasSupervisorCall(first_result) && guest.svc == 6 &&
                                 guest.pc == second_svc_pc;

    const auto trampoline_it = trampolines.find(second_svc_pc);
    const bool trampoline_ok = trampoline_it != trampolines.end();
    if (!trampoline_ok) {
        CurrentNceContext::Clear();
        Report("IMP008_D2_POST_SVC_TRAMPOLINE_MAP", false);
        return 1;
    }

    // PhysicalCore enters the next RunThread epoch with the context locked. The generated post-SVC
    // trampoline must unlock it, run guest code on the guest stack, then the next SVC must restore
    // host bounds before returning to this C++ frame.
    guest.cpu_registers[0] = ResumeX0;
    params.lock.store(LockLocked, std::memory_order_release);

    const auto second_result = Core::NCE::WindowsNceEnterGuest(
        &guest, reinterpret_cast<const void*>(trampoline_it->second));

    const bool second_return_ok = HasSupervisorCall(second_result) && guest.svc == 7;
    const bool second_host_pair_ok =
        reinterpret_cast<std::uint64_t>(tib->StackBase) == host_stack_base &&
        reinterpret_cast<std::uint64_t>(tib->StackLimit) == host_stack_limit;
    const bool x18_after = ReadPhysicalX18() == teb_address;

    params.lock.store(LockUnlocked, std::memory_order_release);
    CurrentNceContext::Clear();

    Report("IMP008_D2_PATCH_MODE", mode_ok);
    Report("IMP008_D2_RELOCATE", relocate_ok);
    Report("IMP008_D2_ENTRY_CAPTURE_STUB", stub_ok);
    Report("IMP008_D2_GUEST_TEB_ENTRY_PAIR", guest_entry_pair_ok);
    Report("IMP008_D2_FIRST_HOST_RETURN_PAIR", first_host_pair_ok);
    Report("IMP008_D2_FIRST_SVC_RETURN", first_return_ok);
    Report("IMP008_D2_POST_SVC_TRAMPOLINE_MAP", trampoline_ok);
    Report("IMP008_D2_POST_SVC_REENTRY", second_return_ok);
    Report("IMP008_D2_SECOND_HOST_RETURN_PAIR", second_host_pair_ok);
    Report("IMP008_D2_PHYSICAL_X18_TEB_BEFORE", x18_before);
    Report("IMP008_D2_PHYSICAL_X18_TEB_AFTER", x18_after);

    const bool pass = patch_ok && mode_ok && relocate_ok && stub_ok && guest_entry_pair_ok &&
                      first_host_pair_ok && first_return_ok && trampoline_ok && second_return_ok &&
                      second_host_pair_ok && x18_before && x18_after;
    Report("IMP008_D2_TEB_COHERENCE_GATE", pass);
    return pass ? 0 : 1;
#endif
}
