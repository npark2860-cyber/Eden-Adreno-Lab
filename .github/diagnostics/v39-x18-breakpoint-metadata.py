#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v39-x18-breakpoint-metadata.py <arm_nce_windows.cpp>")

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
    """#include <atomic>\n#include <cstdint>\n#include <cstdio>\n#include <cstring>\n#include <limits>\n""",
)

cpp = replace_once(
    cpp,
    "v39-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV39ProbeFileName[] = "eden_nce_v39_x18_breakpoint_metadata.log";
constexpr std::uintptr_t WindowsNceV39TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV39TargetTrampolineAllocationOffset = 0x1F25BC;

thread_local u64 g_windows_nce_v39_selected_seq{};
thread_local u64 g_windows_nce_v39_active_seq{};
thread_local bool g_windows_nce_v39_active{};
thread_local bool g_windows_nce_v39_logging_exception{};

void WriteWindowsNceV39LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV39Line(const char* line) noexcept {
    WriteWindowsNceV39LineToPath(WindowsNceV39ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV39ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV39ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV39ProbeFileName[i];
    }
    WriteWindowsNceV39LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV39ProbeTarget(u64 pc, const void* trampoline) noexcept {
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

    return pc_value - pc_allocation == WindowsNceV39TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV39TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV39Entry(const char* marker, u64 seq, const GuestContext& guest,
                             const void* trampoline) noexcept {
    char line[512]{};
    std::snprintf(line, sizeof(line),
                  "%s seq=%llu tid=%lu pc=0x%016llX sp=0x%016llX svc=0x%08X trampoline=%p",
                  marker, static_cast<unsigned long long>(seq),
                  static_cast<unsigned long>(GetCurrentThreadId()),
                  static_cast<unsigned long long>(guest.pc),
                  static_cast<unsigned long long>(guest.sp),
                  static_cast<unsigned int>(guest.svc), trampoline);
    WriteWindowsNceV39Line(line);
}

void WriteWindowsNceV39BreakpointAudit(const EXCEPTION_RECORD& record,
                                       const ARM64_NT_CONTEXT& context,
                                       const GuestContext& guest,
                                       const NCE::X18FallbackMetadata& metadata) noexcept {
    if (g_windows_nce_v39_logging_exception ||
        record.ExceptionCode != EXCEPTION_BREAKPOINT) {
        return;
    }
    g_windows_nce_v39_logging_exception = true;

    u32 instruction_word{};
    MEMORY_BASIC_INFORMATION pc_mbi{};
    const bool pc_readable =
        VirtualQuery(reinterpret_cast<const void*>(context.Pc), &pc_mbi, sizeof(pc_mbi)) != 0 &&
        pc_mbi.State == MEM_COMMIT &&
        (pc_mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) == 0;
    if (pc_readable) {
        std::memcpy(&instruction_word, reinterpret_cast<const void*>(context.Pc),
                    sizeof(instruction_word));
    }

    const auto exact = NCE::WindowsX18FallbackTrap::FindOriginalInstruction(context.Pc, metadata);
    u64 nearest_pc{};
    u64 nearest_value{};
    u64 nearest_abs_delta = (std::numeric_limits<u64>::max)();
    s64 nearest_signed_delta{};
    u64 metadata_count{};

    for (const auto& [key, value] : metadata) {
        if ((key & NCE::X18SitePatcher::MetadataKeyBit) == 0 ||
            static_cast<u32>(value >> 32) != NCE::X18SitePatcher::MetadataMagic) {
            continue;
        }
        ++metadata_count;
        const u64 runtime_pc = key & ~NCE::X18SitePatcher::MetadataKeyBit;
        const u64 abs_delta = runtime_pc >= context.Pc ? runtime_pc - context.Pc
                                                       : context.Pc - runtime_pc;
        if (abs_delta < nearest_abs_delta) {
            nearest_abs_delta = abs_delta;
            nearest_pc = runtime_pc;
            nearest_value = value;
            nearest_signed_delta = runtime_pc >= context.Pc
                                       ? static_cast<s64>(runtime_pc - context.Pc)
                                       : -static_cast<s64>(context.Pc - runtime_pc);
        }
    }

    if (nearest_abs_delta == (std::numeric_limits<u64>::max)()) {
        nearest_abs_delta = 0;
        nearest_signed_delta = 0;
    }

    char line[1280]{};
    std::snprintf(
        line, sizeof(line),
        "V39_BREAKPOINT seq=%llu tid=%lu exception_addr=%p context_pc=0x%016llX "
        "context_sp=0x%016llX pc_readable=%u word=0x%08X is_x18_brk=%u exact_hit=%u "
        "exact_original=0x%08X metadata_count=%llu nearest_pc=0x%016llX "
        "nearest_delta=%lld nearest_abs_delta=0x%016llX nearest_value=0x%016llX "
        "nearest_original=0x%08X guest_pc=0x%016llX guest_sp=0x%016llX guest_svc=0x%08X",
        static_cast<unsigned long long>(g_windows_nce_v39_active_seq),
        static_cast<unsigned long>(GetCurrentThreadId()), record.ExceptionAddress,
        static_cast<unsigned long long>(context.Pc),
        static_cast<unsigned long long>(context.Sp), pc_readable ? 1U : 0U,
        static_cast<unsigned int>(instruction_word),
        instruction_word == NCE::X18SitePatcher::BreakpointInstruction ? 1U : 0U,
        exact.has_value() ? 1U : 0U,
        static_cast<unsigned int>(exact.value_or(0)),
        static_cast<unsigned long long>(metadata_count),
        static_cast<unsigned long long>(nearest_pc),
        static_cast<long long>(nearest_signed_delta),
        static_cast<unsigned long long>(nearest_abs_delta),
        static_cast<unsigned long long>(nearest_value),
        static_cast<unsigned int>(nearest_value),
        static_cast<unsigned long long>(guest.pc),
        static_cast<unsigned long long>(guest.sp), static_cast<unsigned int>(guest.svc));
    WriteWindowsNceV39Line(line);
    g_windows_nce_v39_logging_exception = false;
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "v39-veh-observer",
    """    auto* const thread = nce->m_running_thread;\n    auto* const process = thread->GetOwnerProcess();\n    auto* const params = &thread->GetNativeExecutionParameters();\n\n    // IMP-006 ordinary guest-x18 sites deliberately trap with BRK #0xF000. Once the tagged\n""",
    """    auto* const thread = nce->m_running_thread;\n    auto* const process = thread->GetOwnerProcess();\n    auto* const params = &thread->GetNativeExecutionParameters();\n\n    if (g_windows_nce_v39_active) {\n        WriteWindowsNceV39BreakpointAudit(*exception->ExceptionRecord, context, *guest,\n                                          process->GetPostHandlers());\n    }\n\n    // IMP-006 ordinary guest-x18 sites deliberately trap with BRK #0xF000. Once the tagged\n""",
)

cpp = replace_once(
    cpp,
    "v39-entry-observer",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const actual_trampoline = reinterpret_cast<const void*>(it->second);\n            const bool v39_probe = IsWindowsNceV39ProbeTarget(m_guest_ctx.pc, actual_trampoline);\n            u64 v39_seq = 0;\n            if (v39_probe) {\n                v39_seq = ++g_windows_nce_v39_selected_seq;\n                g_windows_nce_v39_active_seq = v39_seq;\n                g_windows_nce_v39_active = true;\n                WriteWindowsNceV39Entry(\"V39_ENTER\", v39_seq, m_guest_ctx, actual_trampoline);\n            }\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, actual_trampoline));\n            if (v39_probe) {\n                WriteWindowsNceV39Entry(\"V39_RETURN\", v39_seq, m_guest_ctx, actual_trampoline);\n                g_windows_nce_v39_active = false;\n                g_windows_nce_v39_active_seq = 0;\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")

updated = cpp_path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v39_x18_breakpoint_metadata.log",
    "V39_ENTER",
    "V39_RETURN",
    "V39_BREAKPOINT",
    "BreakpointInstruction",
    "nearest_delta",
    "exact_hit",
]:
    if marker not in updated:
        raise SystemExit(f"missing V39 marker in {cpp_path}: {marker}")

for stale in ["V38_EXCEPTION", "V37_ENTER", "V36_PENDING", "V35_BRANCH_AUDIT"]:
    if stale in updated:
        raise SystemExit(f"unexpected prior diagnostic marker in V39 source: {stale}")

print("REALGAME_V39_X18_BREAKPOINT_METADATA=PASS")
