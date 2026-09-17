#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v29-post-entry-detail.py <arm_nce_windows.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(label: str, old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    text = text.replace(old, new, 1)

replace_once(
    "cstdio-include",
    """#include <atomic>\n#include <cstdint>\n""",
    """#include <atomic>\n#include <cstdint>\n#include <cstdio>\n""",
)

replace_once(
    "detail-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    r'''std::once_flag g_windows_veh_once;
PVOID g_windows_veh_handle{};

constexpr char WindowsNceV29DetailFileName[] = "eden_nce_v29_post_detail.log";

void WriteWindowsNceV29LineToPath(const char* path, const char* line) noexcept {
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

void WriteWindowsNceV29Line(const char* line) noexcept {
    WriteWindowsNceV29LineToPath(WindowsNceV29DetailFileName, line);
    char temp_path[MAX_PATH]{};
    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);
    if (temp_length == 0 || temp_length >= MAX_PATH ||
        temp_length + sizeof(WindowsNceV29DetailFileName) > MAX_PATH) {
        return;
    }
    for (DWORD i = 0; i < sizeof(WindowsNceV29DetailFileName); ++i) {
        temp_path[temp_length + i] = WindowsNceV29DetailFileName[i];
    }
    WriteWindowsNceV29LineToPath(temp_path, line);
}

void WriteWindowsNceV29PostDetail(u64 pc, u64 sp, const void* trampoline) noexcept {
    MEMORY_BASIC_INFORMATION pc_mbi{};
    MEMORY_BASIC_INFORMATION sp_mbi{};
    MEMORY_BASIC_INFORMATION tramp_mbi{};
    const SIZE_T pc_query = VirtualQuery(reinterpret_cast<const void*>(pc), &pc_mbi, sizeof(pc_mbi));
    const SIZE_T sp_query = sp != 0
                                ? VirtualQuery(reinterpret_cast<const void*>(sp - 1), &sp_mbi,
                                               sizeof(sp_mbi))
                                : 0;
    const SIZE_T tramp_query = VirtualQuery(trampoline, &tramp_mbi, sizeof(tramp_mbi));

    char line[1024]{};
    std::snprintf(
        line, sizeof(line),
        "V29_POST_ENTER pc=0x%016llX sp=0x%016llX trampoline=%p "
        "pc_q=%llu pc_base=%p pc_alloc=%p pc_state=0x%lX pc_protect=0x%lX pc_type=0x%lX "
        "sp_q=%llu sp_base=%p sp_alloc=%p sp_state=0x%lX sp_protect=0x%lX sp_type=0x%lX "
        "tramp_q=%llu tramp_base=%p tramp_alloc=%p tramp_state=0x%lX tramp_protect=0x%lX tramp_type=0x%lX",
        static_cast<unsigned long long>(pc), static_cast<unsigned long long>(sp), trampoline,
        static_cast<unsigned long long>(pc_query), pc_mbi.BaseAddress, pc_mbi.AllocationBase,
        static_cast<unsigned long>(pc_mbi.State), static_cast<unsigned long>(pc_mbi.Protect),
        static_cast<unsigned long>(pc_mbi.Type),
        static_cast<unsigned long long>(sp_query), sp_mbi.BaseAddress, sp_mbi.AllocationBase,
        static_cast<unsigned long>(sp_mbi.State), static_cast<unsigned long>(sp_mbi.Protect),
        static_cast<unsigned long>(sp_mbi.Type),
        static_cast<unsigned long long>(tramp_query), tramp_mbi.BaseAddress, tramp_mbi.AllocationBase,
        static_cast<unsigned long>(tramp_mbi.State), static_cast<unsigned long>(tramp_mbi.Protect),
        static_cast<unsigned long>(tramp_mbi.Type));
    WriteWindowsNceV29Line(line);
}

void WriteWindowsNceV29VehDetail(PEXCEPTION_POINTERS exception) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return;
    }
    const auto& record = *exception->ExceptionRecord;
    const auto& context = *reinterpret_cast<const ARM64_NT_CONTEXT*>(exception->ContextRecord);
    const ULONG_PTR info0 = record.NumberParameters > 0 ? record.ExceptionInformation[0] : 0;
    const ULONG_PTR info1 = record.NumberParameters > 1 ? record.ExceptionInformation[1] : 0;
    char line[512]{};
    std::snprintf(
        line, sizeof(line),
        "V29_VEH code=0x%08lX exception_address=%p ctx_pc=0x%016llX ctx_sp=0x%016llX "
        "params=%lu info0=0x%016llX info1=0x%016llX",
        static_cast<unsigned long>(record.ExceptionCode), record.ExceptionAddress,
        static_cast<unsigned long long>(context.Pc), static_cast<unsigned long long>(context.Sp),
        static_cast<unsigned long>(record.NumberParameters),
        static_cast<unsigned long long>(info0), static_cast<unsigned long long>(info1));
    WriteWindowsNceV29Line(line);
}

struct WindowsTebStackBounds {
''',
)

replace_once(
    "veh-entry-detail",
    """LONG CALLBACK WindowsNceVectoredExceptionHandler(PEXCEPTION_POINTERS exception) noexcept {\n    if (exception == nullptr || exception->ExceptionRecord == nullptr ||\n        exception->ContextRecord == nullptr) {\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n\n    auto* const guest = NCE::WindowsExceptionContext::CurrentGuestContext();\n""",
    """LONG CALLBACK WindowsNceVectoredExceptionHandler(PEXCEPTION_POINTERS exception) noexcept {\n    if (exception == nullptr || exception->ExceptionRecord == nullptr ||\n        exception->ContextRecord == nullptr) {\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n\n    if (exception->ExceptionRecord->ExceptionCode != EXCEPTION_BREAKPOINT) {\n        WriteWindowsNceV29VehDetail(exception);\n    }\n\n    auto* const guest = NCE::WindowsExceptionContext::CurrentGuestContext();\n""",
)

replace_once(
    "post-entry-detail",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            WriteWindowsNceV29PostDetail(\n                m_guest_ctx.pc, m_guest_ctx.sp, reinterpret_cast<const void*>(it->second));\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")
updated = path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v29_post_detail.log",
    "V29_POST_ENTER",
    "V29_VEH",
    "WriteWindowsNceV29PostDetail",
    "WriteWindowsNceV29VehDetail",
]:
    if marker not in updated:
        raise SystemExit(f"missing V29 marker: {marker}")

print("REALGAME_V29_POST_ENTRY_DETAIL=PASS")
