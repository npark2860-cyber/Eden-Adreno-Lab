#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>

#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "core/arm/nce/windows_cross_thread_break.h"
#include "core/arm/nce/windows_nce_transition.h"

using namespace Core;
using namespace Core::NCE;

extern "C" [[noreturn]] void Imp005GuestLoop(volatile LONG* entered);

namespace {

constexpr SIZE_T StackSize = 64 * 1024;
constexpr unsigned char Canary = 0xA5;
constexpr std::uint64_t GuestX18 = 0x1818181818181818ull;
constexpr std::uint64_t GuestX19 = 0x19191919A5A5A5A5ull;
constexpr std::uint64_t GuestX30 = 0x303030305A5A5A5Aull;
constexpr std::uint64_t ReturnMarker = 0x494D503030354F4Bull;
constexpr std::uint64_t V8Lo = 0x8877665544332211ull;
constexpr std::uint64_t V8Hi = 0x1122334455667788ull;
constexpr DWORD NzcvMask = 0xF0000000u;
constexpr DWORD GuestNzcv = 0xA0000000u;

GuestContext guest{};
WindowsCrossThreadBreak breaker{};
void* stack_mem{};
volatile LONG entered{};
volatile LONG veh_seen{};
volatile LONG veh_host_stack{};
volatile LONG break_ok{};

bool StackIntact() {
    const auto* bytes = static_cast<const unsigned char*>(stack_mem);
    for (SIZE_T i = 0; i < StackSize; ++i) {
        if (bytes[i] != Canary) {
            return false;
        }
    }
    return true;
}

LONG CALLBACK Veh(EXCEPTION_POINTERS* exception) {
    if (!WindowsNceTransition::IsEntryBreakpoint(*exception)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    InterlockedExchange(&veh_seen, 1);

    std::uint64_t local{};
    const auto local_address = reinterpret_cast<std::uintptr_t>(&local);
    const auto* tib = reinterpret_cast<const NT_TIB*>(NtCurrentTeb());
    const auto low = reinterpret_cast<std::uintptr_t>(tib->StackLimit);
    const auto high = reinterpret_cast<std::uintptr_t>(tib->StackBase);
    InterlockedExchange(&veh_host_stack,
                        local_address >= low && local_address < high ? 1 : -1);

    WindowsNceTransition::PrepareGuestEntry(
        guest, *reinterpret_cast<ARM64_NT_CONTEXT*>(exception->ContextRecord));
    return EXCEPTION_CONTINUE_EXECUTION;
}

bool Transform(ARM64_NT_CONTEXT& context, void*) noexcept {
    WindowsNceTransition::RedirectToHost(context, guest, true, ReturnMarker);
    return true;
}

DWORD WINAPI Helper(void*) {
    const ULONGLONG deadline = GetTickCount64() + 5000;
    while (InterlockedCompareExchange(&entered, 0, 0) == 0) {
        if (GetTickCount64() >= deadline) {
            return 2;
        }
        SwitchToThread();
    }

    InterlockedExchange(&break_ok,
                        breaker.SuspendTransformResume(&Transform, nullptr) ? 1 : -1);
    return 0;
}

} // namespace

int main() {
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    if (__getReg(18) != teb) {
        std::printf("X18_BASELINE=FAIL\n");
        return 2;
    }

    if (!breaker.BindCurrentThread()) {
        std::printf("BIND_CURRENT_THREAD=FAIL\n");
        return 3;
    }

    stack_mem = VirtualAlloc(nullptr, StackSize, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (stack_mem == nullptr) {
        return 4;
    }
    std::memset(stack_mem, Canary, StackSize);
    const auto guest_sp =
        (reinterpret_cast<std::uintptr_t>(stack_mem) + StackSize - 0x100) &
        ~std::uintptr_t{0xF};

    ARM64_NT_CONTEXT baseline{};
    RtlCaptureContext(reinterpret_cast<PCONTEXT>(&baseline));

    guest.sp = guest_sp;
    guest.pc = reinterpret_cast<std::uintptr_t>(&Imp005GuestLoop);
    guest.cpu_registers[0] = reinterpret_cast<std::uintptr_t>(&entered);
    guest.cpu_registers[18] = GuestX18;
    guest.cpu_registers[19] = GuestX19;
    guest.cpu_registers[30] = GuestX30;
    std::uint64_t v8[2]{V8Lo, V8Hi};
    std::memcpy(&guest.vector_registers[8], v8, sizeof(v8));
    guest.pstate = (baseline.Cpsr & ~NzcvMask) | GuestNzcv;
    guest.fpcr = baseline.Fpcr;
    guest.fpsr = baseline.Fpsr;

    PVOID veh = AddVectoredExceptionHandler(1, &Veh);
    if (veh == nullptr) {
        return 5;
    }

    const auto host_x19 = __getReg(19);
    const auto host_d8 = std::bit_cast<std::uint64_t>(__getRegFp(8));

    HANDLE helper = CreateThread(nullptr, 0, &Helper, nullptr, 0, nullptr);
    if (helper == nullptr) {
        return 6;
    }

    const auto result = WindowsNceEnterGuest(&guest);
    WaitForSingleObject(helper, 5000);

    std::uint64_t saved_v8[2]{};
    std::memcpy(saved_v8, &guest.vector_registers[8], sizeof(saved_v8));

    const bool return_ok = result == ReturnMarker;
    const bool guest_gpr_ok = guest.cpu_registers[19] == GuestX19 &&
                              guest.cpu_registers[30] == GuestX30 && guest.sp == guest_sp;
    const bool guest_v8_ok = saved_v8[0] == V8Lo && saved_v8[1] == V8Hi;
    const bool guest_x18_virtual_ok = guest.cpu_registers[18] == GuestX18;
    const bool guest_nzcv_ok = (guest.pstate & NzcvMask) == GuestNzcv;
    const bool host_abi_ok = __getReg(18) == teb && __getReg(19) == host_x19 &&
                             std::bit_cast<std::uint64_t>(__getRegFp(8)) == host_d8;
    const bool canary_ok = StackIntact();

    std::printf("VEH_SEEN=%s\n", veh_seen == 1 ? "YES" : "NO");
    std::printf("VEH_HOST_STACK=%s\n", veh_host_stack == 1 ? "YES" : "NO");
    std::printf("BREAK_OK=%s\n", break_ok == 1 ? "YES" : "NO");
    std::printf("RETURN_MARKER_OK=%s\n", return_ok ? "YES" : "NO");
    std::printf("GUEST_GPR_OK=%s\n", guest_gpr_ok ? "YES" : "NO");
    std::printf("GUEST_V8_OK=%s\n", guest_v8_ok ? "YES" : "NO");
    std::printf("GUEST_VIRTUAL_X18_OK=%s\n", guest_x18_virtual_ok ? "YES" : "NO");
    std::printf("GUEST_NZCV_OK=%s\n", guest_nzcv_ok ? "YES" : "NO");
    std::printf("HOST_ABI_X18_OK=%s\n", host_abi_ok ? "YES" : "NO");
    std::printf("GUEST_STACK_CANARY_INTACT=%s\n", canary_ok ? "YES" : "NO");

    const bool pass = veh_seen == 1 && veh_host_stack == 1 && break_ok == 1 && return_ok &&
                      guest_gpr_ok && guest_v8_ok && guest_x18_virtual_ok && guest_nzcv_ok &&
                      host_abi_ok && canary_ok;
    std::printf("WINDOWS_NCE_FIXED_ENTRY_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 20;
}
