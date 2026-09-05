#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <array>
#include <atomic>
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
constexpr std::size_t AllocationSize = 0x10000;
constexpr std::size_t EntryOffset = 0x24;
constexpr std::size_t GuestStackSize = 0x10000;

constexpr std::uint32_t Svc9 = 0xD4000121u;
constexpr std::uint32_t Brk = 0xD4200000u;
constexpr std::uint32_t LockUnlocked = 1;

static_assert(SVC{Svc9}.Verify() && SVC{Svc9}.GetValue() == 9);

constexpr std::uint64_t GuestX0 = 0x1010101010101010ull;
constexpr std::uint64_t GuestX16 = 0x1616161616161616ull;
constexpr std::uint64_t GuestX17 = 0x1717171717171717ull;
constexpr std::uint64_t GuestX18 = 0x1818181818181818ull;
constexpr std::uint32_t GuestNzcv = 0xA0000000u;

std::uint64_t ReadPhysicalX18() {
    std::uint64_t value{};
    asm volatile("mov %0, x18" : "=r"(value));
    return value;
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
    words[EntryOffset / 4] = Svc9;
    words[EntryOffset / 4 + 1] = Brk;

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
        Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_PATCH_MODE", mode_ok);
        return 1;
    }

    EntryTrampolines trampolines;
    const bool relocate_ok = patcher.RelocateAndCopy(
        Common::ProcessAddress{reinterpret_cast<std::uintptr_t>(allocation.base)}, code, image,
        &trampolines);
    if (!relocate_ok || image.size() > AllocationSize) {
        Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_RELOCATE", false);
        return 1;
    }

    std::memcpy(allocation.base, image.data(), image.size());
    if (!FlushInstructionCache(GetCurrentProcess(), allocation.base, image.size())) {
        Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_ICACHE", false);
        return 1;
    }

    std::array<std::uint8_t, GuestStackSize> guest_stack{};
    const auto guest_stack_top =
        reinterpret_cast<std::uintptr_t>(guest_stack.data() + guest_stack.size()) &
        ~std::uintptr_t{0xF};

    const auto guest_pc = reinterpret_cast<std::uintptr_t>(allocation.base) + EntryOffset;
    const auto next_pc = guest_pc + 4;

    GuestContext guest{};
    guest.sp = guest_stack_top;
    guest.pc = guest_pc;
    guest.pstate = GuestNzcv;
    guest.cpu_registers[0] = GuestX0;
    guest.cpu_registers[16] = GuestX16;
    guest.cpu_registers[17] = GuestX17;
    guest.cpu_registers[18] = GuestX18;

    CurrentNceContext::Parameters params{};
    params.native_context = &guest;
    params.lock.store(LockUnlocked, std::memory_order_release);
    CurrentNceContext::Install(&params);

    const auto result = Core::NCE::WindowsNceEnterGuestContext(&guest);
    CurrentNceContext::Clear();

    const bool host_return_ok = HasSupervisorCall(result);
    const bool svc_ok = guest.svc == 9;
    const bool pc_ok = guest.pc == next_pc;
    const bool x0_ok = guest.cpu_registers[0] == GuestX0;
    const bool x16_ok = guest.cpu_registers[16] == GuestX16;
    const bool x17_ok = guest.cpu_registers[17] == GuestX17;
    const bool x18_virtual_ok = guest.cpu_registers[18] == GuestX18;

    params.lock.store(LockUnlocked, std::memory_order_release);
    const bool x18_after = ReadPhysicalX18() == teb;

    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_PATCH_MODE", mode_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_RELOCATE", relocate_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_HOST_RETURN", host_return_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_SVC_ID", svc_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_NEXT_PC", pc_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_X0", x0_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_X16", x16_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_X17", x17_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_VIRTUAL_X18", x18_virtual_ok);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_PHYSICAL_X18_TEB_BEFORE", x18_before);
    Report("IMP008A_PRODUCTION_CONTEXT_ENTRY_PHYSICAL_X18_TEB_AFTER", x18_after);

    const bool pass = patch_ok && mode_ok && relocate_ok && host_return_ok && svc_ok && pc_ok &&
                      x0_ok && x16_ok && x17_ok && x18_virtual_ok && x18_before && x18_after;
    std::printf("IMP008A_WINDOWS_PRODUCTION_ARBITRARY_PC_ENTRY_SMOKE=%s\n",
                pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
