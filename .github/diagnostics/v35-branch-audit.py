#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v35-branch-audit.py <arm_nce_windows.cpp>")

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
    "v35-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV35ProbeFileName[] = "eden_nce_v35_branch_audit.log";
constexpr std::uintptr_t WindowsNceV35TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV35TargetTrampolineAllocationOffset = 0x1F25BC;
constexpr std::uintptr_t WindowsNceV35ScanBytes = 0x1000;

void WriteWindowsNceV35LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV35Line(const char* line) noexcept {
    WriteWindowsNceV35LineToPath(WindowsNceV35ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV35ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV35ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV35ProbeFileName[i];
    }
    WriteWindowsNceV35LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV35ProbeTarget(u64 pc, const void* trampoline) noexcept {
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

    return pc_value - pc_allocation == WindowsNceV35TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV35TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV35Probe(const char* marker, u64 pc, u64 sp,
                             const void* trampoline) noexcept {
    char line[384]{};
    std::snprintf(line, sizeof(line),
                  "%s pc=0x%016llX sp=0x%016llX trampoline=%p",
                  marker, static_cast<unsigned long long>(pc),
                  static_cast<unsigned long long>(sp), trampoline);
    WriteWindowsNceV35Line(line);
}

void WriteWindowsNceV35BranchAudit(u64 pc, const void* trampoline) noexcept {
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(trampoline, &mbi, sizeof(mbi)) == 0 || mbi.BaseAddress == nullptr ||
        mbi.RegionSize < sizeof(std::uint32_t)) {
        WriteWindowsNceV35Line("V35_BRANCH_AUDIT_QUERY_FAILED");
        return;
    }

    const auto start = reinterpret_cast<std::uintptr_t>(trampoline);
    const auto region_base = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
    const auto region_end = region_base + static_cast<std::uintptr_t>(mbi.RegionSize);
    std::uintptr_t scan_end = start + WindowsNceV35ScanBytes;
    if (scan_end < start || scan_end > region_end) {
        scan_end = region_end;
    }

    std::uint64_t b_count{};
    std::uint64_t exact_count{};
    std::uintptr_t exact_addr{};
    std::uintptr_t exact_target{};
    std::uint32_t exact_word{};
    std::uintptr_t closest_addr{};
    std::uintptr_t closest_target{};
    std::uint32_t closest_word{};
    std::uint64_t closest_delta = ~std::uint64_t{0};
    const auto expected = static_cast<std::uintptr_t>(pc);

    for (std::uintptr_t address = start; address + sizeof(std::uint32_t) <= scan_end;
         address += sizeof(std::uint32_t)) {
        const auto word = *reinterpret_cast<const std::uint32_t*>(address);
        if ((word & 0xFC000000U) != 0x14000000U) {
            continue;
        }

        ++b_count;
        std::int64_t imm26 = static_cast<std::int64_t>(word & 0x03FFFFFFU);
        if ((imm26 & 0x02000000LL) != 0) {
            imm26 -= 0x04000000LL;
        }
        const auto byte_offset = imm26 * 4;
        const auto decoded = static_cast<std::uintptr_t>(
            static_cast<std::int64_t>(address) + byte_offset);
        const auto delta = decoded >= expected ? static_cast<std::uint64_t>(decoded - expected)
                                               : static_cast<std::uint64_t>(expected - decoded);

        if (delta < closest_delta) {
            closest_delta = delta;
            closest_addr = address;
            closest_target = decoded;
            closest_word = word;
        }
        if (decoded == expected) {
            ++exact_count;
            if (exact_addr == 0) {
                exact_addr = address;
                exact_target = decoded;
                exact_word = word;
            }
        }
    }

    char line[768]{};
    std::snprintf(
        line, sizeof(line),
        "V35_BRANCH_AUDIT pc=0x%016llX trampoline=%p scan_end=%p b_count=%llu "
        "exact_count=%llu exact_addr=%p exact_word=0x%08X exact_target=0x%016llX "
        "closest_addr=%p closest_word=0x%08X closest_target=0x%016llX closest_delta=0x%llX",
        static_cast<unsigned long long>(pc), trampoline,
        reinterpret_cast<const void*>(scan_end), static_cast<unsigned long long>(b_count),
        static_cast<unsigned long long>(exact_count), reinterpret_cast<const void*>(exact_addr),
        static_cast<unsigned int>(exact_word), static_cast<unsigned long long>(exact_target),
        reinterpret_cast<const void*>(closest_addr), static_cast<unsigned int>(closest_word),
        static_cast<unsigned long long>(closest_target),
        static_cast<unsigned long long>(closest_delta));
    WriteWindowsNceV35Line(line);
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "post-entry-audit",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const actual_trampoline = reinterpret_cast<const void*>(it->second);\n            const bool v35_probe =\n                IsWindowsNceV35ProbeTarget(m_guest_ctx.pc, actual_trampoline);\n            if (v35_probe) {\n                WriteWindowsNceV35Probe(\"V35_PROBE_ENTER\", m_guest_ctx.pc, m_guest_ctx.sp,\n                                        actual_trampoline);\n                WriteWindowsNceV35BranchAudit(m_guest_ctx.pc, actual_trampoline);\n            }\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, actual_trampoline));\n            if (v35_probe) {\n                WriteWindowsNceV35Probe(\"V35_PRODUCTION_RETURNED\", m_guest_ctx.pc,\n                                        m_guest_ctx.sp, actual_trampoline);\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")

updated = cpp_path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v35_branch_audit.log",
    "V35_PROBE_ENTER",
    "V35_BRANCH_AUDIT",
    "V35_PRODUCTION_RETURNED",
    "WindowsNceV35TargetPcAllocationOffset",
    "0xFC000000U",
]:
    if marker not in updated:
        raise SystemExit(f"missing V35 marker in {cpp_path}: {marker}")

print("REALGAME_V35_BRANCH_AUDIT=PASS")
