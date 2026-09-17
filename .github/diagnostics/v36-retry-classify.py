#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v36-retry-classify.py <arm_nce_windows.cpp>")

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
    "v36-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV36ProbeFileName[] = "eden_nce_v36_retry_classify.log";
constexpr std::uintptr_t WindowsNceV36TargetPcAllocationOffset = 0x1F03764;
constexpr std::uintptr_t WindowsNceV36TargetTrampolineAllocationOffset = 0x1F25BC;

void WriteWindowsNceV36LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV36Line(const char* line) noexcept {
    WriteWindowsNceV36LineToPath(WindowsNceV36ProbeFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV36ProbeFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV36ProbeFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV36ProbeFileName[i];
    }
    WriteWindowsNceV36LineToPath(temp_path, line);
}

[[nodiscard]] bool IsWindowsNceV36ProbeTarget(u64 pc, const void* trampoline) noexcept {
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

    return pc_value - pc_allocation == WindowsNceV36TargetPcAllocationOffset &&
           trampoline_value - trampoline_allocation ==
               WindowsNceV36TargetTrampolineAllocationOffset;
}

void WriteWindowsNceV36Enter(u64 seq, u64 pc, u64 sp, const void* trampoline) noexcept {
    char line[384]{};
    std::snprintf(line, sizeof(line),
                  "V36_ENTER seq=%llu pc=0x%016llX sp=0x%016llX trampoline=%p",
                  static_cast<unsigned long long>(seq), static_cast<unsigned long long>(pc),
                  static_cast<unsigned long long>(sp), trampoline);
    WriteWindowsNceV36Line(line);
}

void WriteWindowsNceV36Return(u64 seq, HaltReason hr, const GuestContext& guest,
                              bool pending, u64 fault_address, u64 fault_page) noexcept {
    char line[640]{};
    std::snprintf(
        line, sizeof(line),
        "V36_RETURN seq=%llu hr=0x%016llX pc=0x%016llX sp=0x%016llX pending=%u "
        "fault_addr=0x%016llX fault_page=0x%016llX esr=0x%016llX",
        static_cast<unsigned long long>(seq),
        static_cast<unsigned long long>(static_cast<u64>(hr)),
        static_cast<unsigned long long>(guest.pc), static_cast<unsigned long long>(guest.sp),
        pending ? 1U : 0U, static_cast<unsigned long long>(fault_address),
        static_cast<unsigned long long>(fault_page),
        static_cast<unsigned long long>(guest.esr_el1.load(std::memory_order_acquire)));
    WriteWindowsNceV36Line(line);
}

void WriteWindowsNceV36Invalidate(u64 seq, u64 fault_address, u64 fault_page,
                                  u64 guest_pc, bool invalidated) noexcept {
    char line[512]{};
    std::snprintf(
        line, sizeof(line),
        "V36_PENDING seq=%llu fault_addr=0x%016llX fault_page=0x%016llX "
        "guest_pc=0x%016llX invalidate=%u",
        static_cast<unsigned long long>(seq), static_cast<unsigned long long>(fault_address),
        static_cast<unsigned long long>(fault_page), static_cast<unsigned long long>(guest_pc),
        invalidated ? 1U : 0U);
    WriteWindowsNceV36Line(line);
}

struct WindowsTebStackBounds {
''',
)

cpp = replace_once(
    cpp,
    "v36-sequence-counter",
    """    const auto& post_handlers = process->GetPostHandlers();\n    std::optional<Common::HostMemory::PrivateMappingLease> private_stack_lease;\n\n    for (;;) {\n""",
    """    const auto& post_handlers = process->GetPostHandlers();\n    std::optional<Common::HostMemory::PrivateMappingLease> private_stack_lease;\n    u64 v36_selected_seq = 0;\n\n    for (;;) {\n""",
)

cpp = replace_once(
    cpp,
    "v36-entry-return-classify",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
    """        bool v36_probe = false;\n        u64 v36_seq = 0;\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            const auto* const actual_trampoline = reinterpret_cast<const void*>(it->second);\n            v36_probe = IsWindowsNceV36ProbeTarget(m_guest_ctx.pc, actual_trampoline);\n            if (v36_probe) {\n                v36_seq = ++v36_selected_seq;\n                WriteWindowsNceV36Enter(v36_seq, m_guest_ctx.pc, m_guest_ctx.sp,\n                                        actual_trampoline);\n            }\n            hr = static_cast<HaltReason>(\n                NCE::WindowsNceEnterGuest(&m_guest_ctx, actual_trampoline));\n            if (v36_probe) {\n                WriteWindowsNceV36Return(v36_seq, hr, m_guest_ctx,\n                                         m_windows_pending_nce_fault,\n                                         m_windows_pending_nce_fault_address,\n                                         m_windows_pending_nce_fault_page);\n            }\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
)

cpp = replace_once(
    cpp,
    "v36-pending-invalidate-classify",
    """            if (process->GetMemory().InvalidateNCE(Common::ProcessAddress{pending_fault_page},\n                                                   Memory::YUZU_PAGESIZE)) {\n                continue;\n            }\n""",
    """            const bool v36_invalidated = process->GetMemory().InvalidateNCE(\n                Common::ProcessAddress{pending_fault_page}, Memory::YUZU_PAGESIZE);\n            if (v36_probe) {\n                WriteWindowsNceV36Invalidate(v36_seq, pending_fault_address,\n                                             pending_fault_page, m_guest_ctx.pc,\n                                             v36_invalidated);\n            }\n            if (v36_invalidated) {\n                continue;\n            }\n""",
)

cpp = replace_once(
    cpp,
    "v36-fallback-classify",
    """        const auto fallback = m_windows_x18_runner->Dispatch(\n            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);\n\n        if (fallback.handled && private_stack_lease.has_value() &&\n""",
    """        const auto fallback = m_windows_x18_runner->Dispatch(\n            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);\n\n        if (v36_probe) {\n            char v36_fallback_line[512]{};\n            std::snprintf(\n                v36_fallback_line, sizeof(v36_fallback_line),\n                \"V36_FALLBACK seq=%llu handled=%u metadata=%u completed=%u halt=0x%016llX pc=0x%016llX\",\n                static_cast<unsigned long long>(v36_seq), fallback.handled ? 1U : 0U,\n                fallback.metadata_found ? 1U : 0U, fallback.step.completed ? 1U : 0U,\n                static_cast<unsigned long long>(static_cast<u64>(fallback.step.halt_reason)),\n                static_cast<unsigned long long>(m_guest_ctx.pc));\n            WriteWindowsNceV36Line(v36_fallback_line);\n        }\n\n        if (fallback.handled && private_stack_lease.has_value() &&\n""",
)

cpp_path.write_text(cpp, encoding="utf-8", newline="\n")

updated = cpp_path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v36_retry_classify.log",
    "V36_ENTER",
    "V36_RETURN",
    "V36_PENDING",
    "V36_FALLBACK",
    "WindowsNceV36TargetPcAllocationOffset",
    "v36_invalidated",
]:
    if marker not in updated:
        raise SystemExit(f"missing V36 marker in {cpp_path}: {marker}")

for stale in ["V35_BRANCH_AUDIT", "V35_PRODUCTION_RETURNED"]:
    if stale in updated:
        raise SystemExit(f"unexpected stale V35 runtime marker in {cpp_path}: {stale}")

print("REALGAME_V36_RETRY_CLASSIFY=PASS")
