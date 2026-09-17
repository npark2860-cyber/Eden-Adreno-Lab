#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v28-transition-early-breadcrumb.py <windows_nce_transition.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(label: str, old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    "breadcrumb-helper",
    """namespace {\nconstexpr std::uint32_t NzcvMask = 0xF0000000U;\n\nvoid TraceVirtualMapping""",
    """namespace {\nconstexpr std::uint32_t NzcvMask = 0xF0000000U;\nconstexpr char WindowsNceV28BreadcrumbFileName[] = \"eden_nce_v28_early.log\";\n\nvoid WriteWindowsNceV28TransitionBreadcrumbToPath(const char* path, const char* marker) noexcept {\n    const HANDLE file = CreateFileA(\n        path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,\n        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);\n    if (file == INVALID_HANDLE_VALUE) {\n        return;\n    }\n    DWORD written{};\n    const DWORD marker_length = static_cast<DWORD>(lstrlenA(marker));\n    if (marker_length != 0) {\n        WriteFile(file, marker, marker_length, &written, nullptr);\n        static constexpr char Newline[] = \"\\r\\n\";\n        WriteFile(file, Newline, static_cast<DWORD>(sizeof(Newline) - 1), &written, nullptr);\n        FlushFileBuffers(file);\n    }\n    CloseHandle(file);\n}\n\nvoid WriteWindowsNceV28TransitionBreadcrumb(const char* marker) noexcept {\n    WriteWindowsNceV28TransitionBreadcrumbToPath(WindowsNceV28BreadcrumbFileName, marker);\n    char temp_path[MAX_PATH]{};\n    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);\n    if (temp_length == 0 || temp_length >= MAX_PATH ||\n        temp_length + sizeof(WindowsNceV28BreadcrumbFileName) > MAX_PATH) {\n        return;\n    }\n    std::memcpy(temp_path + temp_length, WindowsNceV28BreadcrumbFileName,\n                sizeof(WindowsNceV28BreadcrumbFileName));\n    WriteWindowsNceV28TransitionBreadcrumbToPath(temp_path, marker);\n}\n\nvoid TraceVirtualMapping""",
)

replace_once(
    "continue-guest-entry",
    """extern \"C\" [[noreturn]] void WindowsNceContinueGuestContext(\n    ARM64_NT_CONTEXT* context) noexcept {\n    if (context == nullptr) {\n        std::abort();\n    }\n    WindowsNceTransition::ContinueContext(*context);\n}\n""",
    """extern \"C\" [[noreturn]] void WindowsNceContinueGuestContext(\n    ARM64_NT_CONTEXT* context) noexcept {\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_GUEST_STACK_BRIDGE_REACHED\");\n    if (context == nullptr) {\n        WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_GUEST_CONTEXT_NULL\");\n        std::abort();\n    }\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_BEFORE_GUEST_NTCONTINUE\");\n    WindowsNceTransition::ContinueContext(*context);\n}\n""",
)

replace_once(
    "restore-entry",
    """extern \"C\" [[noreturn]] void WindowsNceRestoreGuestContext(GuestContext* guest) noexcept {\n    std::fputs(\"IMP008B_E2_RESTORE_ENTER=PASS\\n\", stderr);\n""",
    """extern \"C\" [[noreturn]] void WindowsNceRestoreGuestContext(GuestContext* guest) noexcept {\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_RESTORE_ENTER\");\n    std::fputs(\"IMP008B_E2_RESTORE_ENTER=PASS\\n\", stderr);\n""",
)

replace_once(
    "context-match",
    """    if (parameters == nullptr || parameters->native_context != guest) {\n        std::abort();\n    }\n    std::fputs(\"IMP008B_E2_RESTORE_CONTEXT_MATCH=PASS\\n\", stderr);\n""",
    """    if (parameters == nullptr || parameters->native_context != guest) {\n        WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_CONTEXT_MISMATCH\");\n        std::abort();\n    }\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_CONTEXT_MATCH\");\n    std::fputs(\"IMP008B_E2_RESTORE_CONTEXT_MATCH=PASS\\n\", stderr);\n""",
)

replace_once(
    "after-unlock",
    """    parameters->lock.store(SpinLockUnlocked, std::memory_order_release);\n\n    std::fprintf(stderr,\n""",
    """    parameters->lock.store(SpinLockUnlocked, std::memory_order_release);\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_AFTER_PARAM_UNLOCK\");\n\n    std::fprintf(stderr,\n""",
)

replace_once(
    "before-stack-query",
    """    MEMORY_BASIC_INFORMATION stack_mbi{};\n    if (VirtualQuery(reinterpret_cast<const void*>(guest->sp - 1), &stack_mbi,\n                     sizeof(stack_mbi)) == 0 ||\n        stack_mbi.AllocationBase == nullptr) {\n        std::abort();\n    }\n""",
    """    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_BEFORE_STACK_QUERY\");\n    MEMORY_BASIC_INFORMATION stack_mbi{};\n    if (VirtualQuery(reinterpret_cast<const void*>(guest->sp - 1), &stack_mbi,\n                     sizeof(stack_mbi)) == 0 ||\n        stack_mbi.AllocationBase == nullptr) {\n        WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_STACK_QUERY_FAILED\");\n        std::abort();\n    }\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_AFTER_STACK_QUERY\");\n""",
)

replace_once(
    "stacktop-check",
    """    if (guest->sp <= allocation_base || guest->sp > allocation_end) {\n        std::abort();\n    }\n\n    ARM64_NT_CONTEXT bridge_context = context;\n""",
    """    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_BEFORE_STACKTOP_CHECK\");\n    if (guest->sp <= allocation_base || guest->sp > allocation_end) {\n        WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_STACKTOP_REJECTED\");\n        std::abort();\n    }\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_STACKTOP_ACCEPTED\");\n\n    ARM64_NT_CONTEXT bridge_context = context;\n""",
)

replace_once(
    "before-bridge-ntcontinue",
    """    bridge_context.X[1] = static_cast<std::uint64_t>(allocation_end);\n    bridge_context.X[2] = static_cast<std::uint64_t>(allocation_base);\n    WindowsNceTransition::ContinueContext(bridge_context);\n""",
    """    bridge_context.X[1] = static_cast<std::uint64_t>(allocation_end);\n    bridge_context.X[2] = static_cast<std::uint64_t>(allocation_base);\n    WriteWindowsNceV28TransitionBreadcrumb(\"V28_TRANS_BEFORE_BRIDGE_NTCONTINUE\");\n    WindowsNceTransition::ContinueContext(bridge_context);\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")

updated = path.read_text(encoding="utf-8")
for marker in [
    "V28_TRANS_RESTORE_ENTER",
    "V28_TRANS_CONTEXT_MATCH",
    "V28_TRANS_AFTER_STACK_QUERY",
    "V28_TRANS_STACKTOP_ACCEPTED",
    "V28_TRANS_BEFORE_BRIDGE_NTCONTINUE",
    "V28_TRANS_GUEST_STACK_BRIDGE_REACHED",
    "V28_TRANS_BEFORE_GUEST_NTCONTINUE",
]:
    if marker not in updated:
        raise SystemExit(f"missing V28 transition marker: {marker}")

print("REALGAME_V28_TRANSITION_BREADCRUMB=PASS")
