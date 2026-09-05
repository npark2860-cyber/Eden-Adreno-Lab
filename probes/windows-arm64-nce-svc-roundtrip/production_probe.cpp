#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <array>
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
constexpr std::size_t AllocationSize = 0x20000;
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

constexpr std::uint64_t InitialX16 = 0x1616161616161616ull;
constexpr std::uint64_t InitialX17 = 0x1717171717171717ull;
constexpr std::uint64_t InitialX18 = 0x1818181818181818ull;
constexpr std::uint64_t ResumeX0 = 0xA0A0A0A0A0A0A0A0ull;
constexpr std::uint64_t ResumeX16 = 0x2626262626262626ull;
constexpr std::uint64_t ResumeX17 = 0x2727272727272727ull;
constexpr std::uint64_t ResumeX18 = 0x2828282828282828ull;

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
    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    const bool x18_before = ReadPhysicalX18() == teb;

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

    Allocation allocation;
    allocation.base = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, AllocationSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!allocation.base || !mode_ok) {
        Report("IMP008A_SVC_PATCH_MODE", mode_ok);
        return 1;
    }

    EntryTrampolines trampolines;
    const bool relocate_ok = patcher.RelocateAndCopy(
        Common::ProcessAddress{reinterpret_cast<std::uintptr_t>(allocation.base)}, code, image,
        &trampolines);
    if (!relocate_ok || image.size() >= InitialStubOffset) {
        Report("IMP008A_SVC_RELOCATE", false);
        return 1;
    }

    std::memcpy(allocation.base, image.data(), image.size());

    const auto first_svc_pc = reinterpret_cast<std::uintptr_t>(allocation.base) + EntryOffset;
    const auto second_svc_pc = first_svc_pc + 4;
    auto* stub_words = reinterpret_cast<std::uint32_t*>(allocation.base + InitialStubOffset);
    stub_words[0] = EncodeLdrX(16, 17,
                              offsetof(GuestContext, cpu_registers) + sizeof(std::uint64_t) * 16);
    stub_words[1] = EncodeLdrX(17, 17,
                              offsetof(GuestContext, cpu_registers) + sizeof(std::uint64_t) * 17);
    stub_words[2] = EncodeB(reinterpret_cast<std::uintptr_t>(&stub_words[2]), first_svc_pc);
    const bool stub_ok = stub_words[0] != 0 && stub_words[1] != 0 && stub_words[2] != 0;

    if (!stub_ok || !FlushInstructionCache(GetCurrentProcess(), allocation.base, AllocationSize)) {
        Report("IMP008A_INITIAL_DIRECT_ENTRY_STUB", false);
        return 1;
    }

    std::array<std::uint8_t, GuestStackSize> guest_stack{};
    const auto guest_stack_top =
        (reinterpret_cast<std::uintptr_t>(guest_stack.data() + guest_stack.size()) & ~std::uintptr_t{0xF});

    GuestContext guest{};
    guest.sp = guest_stack_top;
    guest.pc = first_svc_pc;
    guest.cpu_registers[16] = InitialX16;
    guest.cpu_registers[17] = InitialX17;
    guest.cpu_registers[18] = InitialX18;

    CurrentNceContext::Parameters params{};
    params.native_context = &guest;
    params.lock.store(LockUnlocked, std::memory_order_release);
    CurrentNceContext::Install(&params);

    const auto first_result = Core::NCE::WindowsNceEnterGuest(
        &guest, allocation.base + InitialStubOffset);
    CurrentNceContext::Clear();

    const bool first_return_ok = HasSupervisorCall(first_result);
    const bool first_svc_ok = guest.svc == 6;
    const bool first_pc_ok = guest.pc == second_svc_pc;
    const bool first_x16_ok = guest.cpu_registers[16] == InitialX16;
    const bool first_x17_ok = guest.cpu_registers[17] == InitialX17;
    const bool first_x18_ok = guest.cpu_registers[18] == InitialX18;

    const auto trampoline_it = trampolines.find(second_svc_pc);
    const bool trampoline_ok = trampoline_it != trampolines.end();
    if (!trampoline_ok) {
        params.lock.store(LockUnlocked, std::memory_order_release);
        Report("IMP008A_POST_SVC_TRAMPOLINE_MAP", false);
        return 1;
    }

    // Simulate PhysicalCore::ExitContext after the first RunThread return.
    params.lock.store(LockUnlocked, std::memory_order_release);

    // Simulate host-side SVC handling changing guest architectural state before the next entry.
    guest.cpu_registers[0] = ResumeX0;
    guest.cpu_registers[16] = ResumeX16;
    guest.cpu_registers[17] = ResumeX17;
    guest.cpu_registers[18] = ResumeX18;

    // Simulate PhysicalCore::EnterContext before the next RunThread call. The generated post-SVC
    // trampoline must release this lock before the second SVC can reacquire it.
    params.lock.store(LockLocked, std::memory_order_release);
    CurrentNceContext::Install(&params);
    const auto second_result = Core::NCE::WindowsNceEnterGuest(
        &guest, reinterpret_cast<const void*>(trampoline_it->second));
    CurrentNceContext::Clear();

    const bool second_return_ok = HasSupervisorCall(second_result);
    const bool second_svc_ok = guest.svc == 7;
    const bool resumed_x0_ok = guest.cpu_registers[0] == ResumeX0;
    const bool resumed_x16_ok = guest.cpu_registers[16] == ResumeX16;
    const bool resumed_x17_ok = guest.cpu_registers[17] == ResumeX17;
    const bool resumed_x18_ok = guest.cpu_registers[18] == ResumeX18;

    // Simulate the second PhysicalCore::ExitContext for clean shutdown.
    params.lock.store(LockUnlocked, std::memory_order_release);

    const bool x18_after = ReadPhysicalX18() == teb;

    Report("IMP008A_SVC_PATCH_MODE", mode_ok);
    Report("IMP008A_SVC_RELOCATE", relocate_ok);
    Report("IMP008A_INITIAL_DIRECT_ENTRY_STUB", stub_ok);
    Report("IMP008A_FIRST_SVC_HOST_RETURN", first_return_ok);
    Report("IMP008A_FIRST_SVC_ID", first_svc_ok);
    Report("IMP008A_FIRST_SVC_NEXT_PC", first_pc_ok);
    Report("IMP008A_FIRST_SAVE_X16", first_x16_ok);
    Report("IMP008A_FIRST_SAVE_X17", first_x17_ok);
    Report("IMP008A_FIRST_VIRTUAL_X18", first_x18_ok);
    Report("IMP008A_POST_SVC_TRAMPOLINE_MAP", trampoline_ok);
    Report("IMP008A_SECOND_SVC_HOST_RETURN", second_return_ok);
    Report("IMP008A_SECOND_SVC_ID", second_svc_ok);
    Report("IMP008A_RESUME_X0", resumed_x0_ok);
    Report("IMP008A_RESUME_X16", resumed_x16_ok);
    Report("IMP008A_RESUME_X17", resumed_x17_ok);
    Report("IMP008A_RESUME_VIRTUAL_X18", resumed_x18_ok);
    Report("IMP008A_PHYSICAL_X18_TEB_BEFORE", x18_before);
    Report("IMP008A_PHYSICAL_X18_TEB_AFTER", x18_after);

    const bool pass = patch_ok && mode_ok && relocate_ok && stub_ok && first_return_ok &&
                      first_svc_ok && first_pc_ok && first_x16_ok && first_x17_ok && first_x18_ok &&
                      trampoline_ok && second_return_ok && second_svc_ok && resumed_x0_ok &&
                      resumed_x16_ok && resumed_x17_ok && resumed_x18_ok && x18_before && x18_after;
    std::printf("IMP008A_WINDOWS_SVC_ROUNDTRIP_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
