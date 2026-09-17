#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v37-svc-epoch-continuity.py <arm_nce_windows.cpp>")

cpp_path = Path(sys.argv[1])
cpp = cpp_path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


cpp = replace_once(
    cpp,
    "cstdio-include",
    """#include <atomic>\n#include <cstdint>\n""",
    """#include <atomic>\n#include <cstdint>\n#include <cstdio>\n""",
)

cpp = replace_once(
    cpp,
    "v37-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV37ProbeFileName[] = "eden_nce_v37_svc_epoch_continuity.log";
constexpr std::uintptr_t WindowsNceV37TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV37TargetTrampolineAllocationOffset = 0x1F25BC;
std::atomic<u64> g_windows_nce_v37_epoch{0};

void WriteWindowsNceV37LineToPath(const char* path, const char* line) noexcept {
    const HANDLE file = CreateFileA(
        path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written{};
    const DWORD length = static_cast<DWORD>(lstrlenA(line));
    if (length != 0) {
        WriteFile(file, line, length, &written, nullptr);
        static constexpr char Newline[] = "\r\n";
        WriteFile(file, Newline, static_cast<DWORD>(sizeof(Newline) - 1), &written, nullptr);
        FlushFileBuffers(file);
    }
    CloseHandle(file);
}

void WriteWindowsNceV37Line(const char* line) noexcept {
    WriteWindowsNceV37LineToPath(WindowsNceV37ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV37ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV37ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV37ProbeFileName[i];
    }
    WriteWindowsNceV37LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV37ProbeTarget(u64 pc, const void* trampoline) noexcept {
    MEMORY_BASIC_INFORMATION pc_mbi{};
    MEMORY_BASIC_INFORMATION tramp_mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(pc), &pc_mbi, sizeof(pc_mbi)) == 0 ||
        VirtualQuery(trampoline, &tramp_mbi, sizeof(tramp_mbi)) == 0 ||
        pc_mbi.AllocationBase == nullptr || tramp_mbi.AllocationBase == nullptr) {
        return false;
    }

    const auto pc_value = static_cast<std::uintptr_t>(pc);
    const auto pc_allocation = reinterpret_cast<std::uintptr_t>(pc_mbi.AllocationBase);
    const auto trampoline_value = reinterpret_cast<std::uintptr_t>(trampoline);
    const auto trampoline_allocation = reinterpret_cast<std::uintptr_t>(tramp_mbi.AllocationBase);
    if (pc_value < pc_allocation || trampoline_value < trampoline_allocation) {
        return false;
    }

    return pc_value - pc_allocation == WindowsNceV37TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV37TargetTrampolineAllocationOffset;
}

[[nodiscard]] u64 WindowsNceV37StackHash(u64 sp) noexcept {
    if (sp == 0) {
        return 0;
    }
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(sp - 1), &mbi, sizeof(mbi)) == 0 ||
        mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return 0;
    }
    const auto base = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
    const auto top = base + static_cast<std::uintptr_t>(mbi.RegionSize);
    const auto sp_value = static_cast<std::uintptr_t>(sp);
    if (sp_value <= base || sp_value > top) {
        return 0;
    }
    const std::uintptr_t start = sp_value - (std::min)(sp_value - base, std::uintptr_t{0x100});
    u64 hash = 1469598103934665603ULL;
    for (std::uintptr_t p = start; p < sp_value; ++p) {
        hash ^= *reinterpret_cast<const u8*>(p);
        hash *= 1099511628211ULL;
    }
    return hash;
}

[[nodiscard]] u32 WindowsNceV37PreviousWord(u64 pc) noexcept {
    if (pc < sizeof(u32)) {
        return 0;
    }
    const auto address = static_cast<std::uintptr_t>(pc - sizeof(u32));
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi)) == 0 ||
        mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return 0;
    }
    return *reinterpret_cast<const u32*>(address);
}

void WriteWindowsNceV37Snapshot(const char* marker, u64 epoch, std::size_t core_index,
                                const void* nce, const void* thread, HaltReason hr,
                                const GuestContext& guest, const void* trampoline) noexcept {
    const u32 prev_word = WindowsNceV37PreviousWord(guest.pc);
    const bool prev_is_svc = (prev_word & 0xFFE0001FU) == 0xD4000001U;
    const u32 prev_svc = prev_is_svc ? ((prev_word >> 5) & 0xFFFFU) : 0xFFFFFFFFU;
    const u64 stack_hash = WindowsNceV37StackHash(guest.sp);
    char line[1536]{};
    std::snprintf(
        line, sizeof(line),
        "%s epoch=%llu core=%llu host_tid=%lu nce=%p thread=%p hr=0x%016llX "
        "pc=0x%016llX sp=0x%016llX svc=0x%08X prev_word=0x%08X prev_svc=0x%08X "
        "stack_hash=0x%016llX x0=0x%016llX x1=0x%016llX x2=0x%016llX x3=0x%016llX "
        "x4=0x%016llX x5=0x%016llX x6=0x%016llX x7=0x%016llX x16=0x%016llX "
        "x17=0x%016llX x18=0x%016llX x29=0x%016llX x30=0x%016llX pstate=0x%08X "
        "nzcv=0x%08X fpcr=0x%08X fpsr=0x%08X tpidr=0x%016llX tpidrro=0x%016llX trampoline=%p",
        marker, static_cast<unsigned long long>(epoch),
        static_cast<unsigned long long>(core_index), GetCurrentThreadId(), nce, thread,
        static_cast<unsigned long long>(static_cast<u64>(hr)),
        static_cast<unsigned long long>(guest.pc), static_cast<unsigned long long>(guest.sp),
        static_cast<unsigned int>(guest.svc), static_cast<unsigned int>(prev_word),
        static_cast<unsigned int>(prev_svc), static_cast<unsigned long long>(stack_hash),
        static_cast<unsigned long long>(guest.cpu_registers[0]),
        static_cast<unsigned long long>(guest.cpu_registers[1]),
        static_cast<unsigned long long>(guest.cpu_registers[2]),
        static_cast<unsigned long long>(guest.cpu_registers[3]),
        static_cast<unsigned long long>(guest.cpu_registers[4]),
        static_cast<unsigned long long>(guest.cpu_registers[5]),
        static_cast<unsigned long long>(guest.cpu_registers[6]),
        static_cast<unsigned long long>(guest.cpu_registers[7]),
        static_cast<unsigned long long>(guest.cpu_registers[16]),
        static_cast<unsigned long long>(guest.cpu_registers[17]),
        static_cast<unsigned long long>(guest.cpu_registers[18]),
        static_cast<unsigned long long>(guest.cpu_registers[29]),
        static_cast<unsigned long long>(guest.cpu_registers[30]),
        static_cast<unsigned int>(guest.pstate), static_cast<unsigned int>(guest.nzcv),
        static_cast<unsigned int>(guest.fpcr), static_cast<unsigned int>(guest.fpsr),
        static_cast<unsigned long long>(guest.tpidr_el0),
        static_cast<unsigned long long>(guest.tpidrro_el0), trampoline);
    WriteWindowsNceV37Line(line);
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "v37-entry-return",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
    """        bool v37_probe = false;\n        u64 v37_epoch = 0;\n        const void* v37_trampoline = nullptr;\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            v37_trampoline = reinterpret_cast<const void*>(it->second);\n            v37_probe = IsWindowsNceV37ProbeTarget(m_guest_ctx.pc, v37_trampoline);\n            if (v37_probe) {\n                v37_epoch = g_windows_nce_v37_epoch.fetch_add(1, std::memory_order_relaxed) + 1;\n                WriteWindowsNceV37Snapshot(\"V37_ENTER\", v37_epoch, m_core_index, this, thread,\n                                           HaltReason{}, m_guest_ctx, v37_trampoline);\n            }\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, v37_trampoline));\n            if (v37_probe) {\n                WriteWindowsNceV37Snapshot(\"V37_RETURN\", v37_epoch, m_core_index, this, thread,\n                                           hr, m_guest_ctx, v37_trampoline);\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")

updated = cpp_path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v37_svc_epoch_continuity.log",
    "V37_ENTER",
    "V37_RETURN",
    "WindowsNceV37StackHash",
    "WindowsNceV37PreviousWord",
    "g_windows_nce_v37_epoch",
]:
    if marker not in updated:
        raise SystemExit(f"missing V37 marker in {cpp_path}: {marker}")

for stale in ["V36_ENTER", "V36_RETURN", "V35_BRANCH_AUDIT", "V35_PRODUCTION_RETURNED"]:
    if stale in updated:
        raise SystemExit(f"unexpected stale runtime marker in V37 source: {stale}")

print("REALGAME_V37_SVC_EPOCH_CONTINUITY=PASS")
