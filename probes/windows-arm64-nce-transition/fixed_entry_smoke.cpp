#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>

#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "core/arm/nce/current_nce_context.h"
#include "core/arm/nce/windows_cross_thread_break.h"
#include "core/arm/nce/windows_nce_transition.h"

using namespace Core;
using namespace Core::NCE;

extern "C" void Imp005EntryTrampoline();
extern "C" [[noreturn]] void Imp005GuestLoop(volatile LONG* entered);

namespace {

constexpr SIZE_T StackSize = 64 * 1024;
constexpr SIZE_T GetterScratchSize = 0x20;
constexpr unsigned char Canary = 0xA5;
constexpr std::uint64_t GuestX16 = 0x16161616A5A5A5A5ull;
constexpr std::uint64_t GuestX17 = 0x171717175A5A5A5Aull;
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
std::uintptr_t guest_sp{};
void* observed_current_context{};
volatile LONG entered{};
volatile LONG break_ok{};

void Mark(const char* text) noexcept {
    DWORD written{};
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), text, static_cast<DWORD>(std::strlen(text)), &written,
              nullptr);
}

bool StackOutsideGetterScratchIntact() {
    const auto* bytes = static_cast<const unsigned char*>(stack_mem);
    const auto low = reinterpret_cast<std::uintptr_t>(stack_mem);
    const auto scratch_low = guest_sp - GetterScratchSize;
    const auto scratch_high = guest_sp;
    for (SIZE_T i = 0; i < StackSize; ++i) {
        const auto address = low + i;
        if (address >= scratch_low && address < scratch_high) {
            continue;
        }
        if (bytes[i] != Canary) {
            return false;
        }
    }
    return true;
}

bool Transform(ARM64_NT_CONTEXT& context, void*) noexcept {
    Mark("BREAK_TRANSFORM_ENTER=YES\n");
    WindowsNceTransition::RedirectToHost(context, guest, true, ReturnMarker);
    Mark("BREAK_TRANSFORM_READY=YES\n");
    return true;
}

DWORD WINAPI Helper(void*) {
    const ULONGLONG deadline = GetTickCount64() + 5000;
    while (InterlockedCompareExchange(&entered, 0, 0) == 0) {
        if (GetTickCount64() >= deadline) {
            Mark("HELPER_GUEST_TIMEOUT=YES\n");
            return 2;
        }
        SwitchToThread();
    }

    Mark("HELPER_SAW_GUEST=YES\n");
    const bool result = breaker.SuspendTransformResume(&Transform, nullptr);
    InterlockedExchange(&break_ok, result ? 1 : -1);
    Mark(result ? "HELPER_BREAK_COMPLETE=YES\n" : "HELPER_BREAK_COMPLETE=NO\n");
    return 0;
}

} // namespace

int main() {
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    Mark("SMOKE_START=YES\n");

    const auto teb = reinterpret_cast<std::uint64_t>(NtCurrentTeb());
    if (__getReg(18) != teb) {
        std::printf("X18_BASELINE=FAIL\n");
        return 2;
    }

    if (!breaker.BindCurrentThread()) {
        std::printf("BIND_CURRENT_THREAD=FAIL\n");
        return 3;
    }
    Mark("THREAD_BOUND=YES\n");

    stack_mem = VirtualAlloc(nullptr, StackSize, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (stack_mem == nullptr) {
        return 4;
    }
    std::memset(stack_mem, Canary, StackSize);
    guest_sp = (reinterpret_cast<std::uintptr_t>(stack_mem) + StackSize - 0x100) &
               ~std::uintptr_t{0xF};

    ARM64_NT_CONTEXT baseline{};
    RtlCaptureContext(reinterpret_cast<PCONTEXT>(&baseline));

    guest.sp = guest_sp;
    guest.pc = reinterpret_cast<std::uintptr_t>(&Imp005GuestLoop);
    guest.cpu_registers[0] = reinterpret_cast<std::uintptr_t>(&entered);
    guest.cpu_registers[2] = reinterpret_cast<std::uintptr_t>(&observed_current_context);
    guest.cpu_registers[16] = GuestX16;
    guest.cpu_registers[17] = GuestX17;
    guest.cpu_registers[18] = GuestX18;
    guest.cpu_registers[19] = GuestX19;
    guest.cpu_registers[30] = GuestX30;
    std::uint64_t v8[2]{V8Lo, V8Hi};
    std::memcpy(&guest.vector_registers[8], v8, sizeof(v8));
    guest.pstate = (baseline.Cpsr & ~NzcvMask) | GuestNzcv;
    guest.fpcr = baseline.Fpcr;
    guest.fpsr = baseline.Fpsr;

    auto* expected_current_context =
        reinterpret_cast<CurrentNceContext::Parameters*>(&guest);
    CurrentNceContext::Install(expected_current_context);

    const auto host_x19 = __getReg(19);
    const auto host_d8 = std::bit_cast<std::uint64_t>(__getRegFp(8));

    HANDLE helper = CreateThread(nullptr, 0, &Helper, nullptr, 0, nullptr);
    if (helper == nullptr) {
        CurrentNceContext::Clear();
        return 5;
    }

    Mark("BEFORE_FIXED_ENTRY=YES\n");
    const auto result =
        WindowsNceEnterGuest(&guest, reinterpret_cast<const void*>(&Imp005EntryTrampoline));
    Mark("AFTER_FIXED_ENTRY=YES\n");
    WaitForSingleObject(helper, 5000);
    CurrentNceContext::Clear();

    std::uint64_t saved_v8[2]{};
    std::memcpy(saved_v8, &guest.vector_registers[8], sizeof(saved_v8));

    const bool return_ok = result == ReturnMarker;
    const bool guest_gpr_ok = guest.cpu_registers[16] == GuestX16 &&
                              guest.cpu_registers[17] == GuestX17 &&
                              guest.cpu_registers[19] == GuestX19 &&
                              guest.cpu_registers[30] == GuestX30 && guest.sp == guest_sp;
    const bool guest_v8_ok = saved_v8[0] == V8Lo && saved_v8[1] == V8Hi;
    const bool guest_x18_virtual_ok = guest.cpu_registers[18] == GuestX18;
    const bool guest_nzcv_ok = (guest.pstate & NzcvMask) == GuestNzcv;
    const bool getter_ok = observed_current_context == expected_current_context;
    const bool host_abi_ok = __getReg(18) == teb && __getReg(19) == host_x19 &&
                             std::bit_cast<std::uint64_t>(__getRegFp(8)) == host_d8;
    const bool stack_bounded_ok = StackOutsideGetterScratchIntact();

    std::printf("BREAK_OK=%s\n", break_ok == 1 ? "YES" : "NO");
    std::printf("RETURN_MARKER_OK=%s\n", return_ok ? "YES" : "NO");
    std::printf("GUEST_GPR_16_17_19_30_OK=%s\n", guest_gpr_ok ? "YES" : "NO");
    std::printf("GUEST_V8_OK=%s\n", guest_v8_ok ? "YES" : "NO");
    std::printf("GUEST_VIRTUAL_X18_OK=%s\n", guest_x18_virtual_ok ? "YES" : "NO");
    std::printf("GUEST_NZCV_OK=%s\n", guest_nzcv_ok ? "YES" : "NO");
    std::printf("GENERATED_TLS_GETTER_OK=%s\n", getter_ok ? "YES" : "NO");
    std::printf("HOST_ABI_X18_OK=%s\n", host_abi_ok ? "YES" : "NO");
    std::printf("GETTER_STACK_BOUNDED_32B=%s\n", stack_bounded_ok ? "YES" : "NO");

    const bool pass = break_ok == 1 && return_ok && guest_gpr_ok && guest_v8_ok &&
                      guest_x18_virtual_ok && guest_nzcv_ok && getter_ok && host_abi_ok &&
                      stack_bounded_ok;
    std::printf("WINDOWS_NCE_FIXED_ENTRY_SMOKE=%s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 20;
}
