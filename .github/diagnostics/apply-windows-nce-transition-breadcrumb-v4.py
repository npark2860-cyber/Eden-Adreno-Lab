from pathlib import Path
import sys

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
    """namespace {\nconstexpr std::uint32_t NzcvMask = 0xF0000000U;\nconstexpr char WindowsNceV4BreadcrumbFileName[] = \"eden_nce_v4_breadcrumb.log\";\n\nvoid WriteWindowsNceV4Breadcrumb(const char* marker) noexcept {\n    char path_buffer[MAX_PATH]{};\n    const DWORD path_length = GetTempPathA(MAX_PATH, path_buffer);\n    if (path_length == 0 || path_length >= MAX_PATH ||\n        path_length + sizeof(WindowsNceV4BreadcrumbFileName) > MAX_PATH) {\n        return;\n    }\n    std::memcpy(path_buffer + path_length, WindowsNceV4BreadcrumbFileName,\n                sizeof(WindowsNceV4BreadcrumbFileName));\n\n    const HANDLE file = CreateFileA(\n        path_buffer, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,\n        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);\n    if (file == INVALID_HANDLE_VALUE) {\n        return;\n    }\n\n    char line[192]{};\n    const int line_length = std::snprintf(\n        line, sizeof(line), \"PID=%lu %s\\r\\n\",\n        static_cast<unsigned long>(GetCurrentProcessId()), marker);\n    if (line_length > 0 && static_cast<std::size_t>(line_length) < sizeof(line)) {\n        DWORD written{};\n        WriteFile(file, line, static_cast<DWORD>(line_length), &written, nullptr);\n        FlushFileBuffers(file);\n    }\n    CloseHandle(file);\n}\n\nvoid TraceVirtualMapping""",
)

replace_once(
    "continue-guest-breadcrumb",
    """extern \"C\" [[noreturn]] void WindowsNceContinueGuestContext(\n    ARM64_NT_CONTEXT* context) noexcept {\n    if (context == nullptr) {\n        std::abort();\n    }\n    WindowsNceTransition::ContinueContext(*context);\n}\n""",
    """extern \"C\" [[noreturn]] void WindowsNceContinueGuestContext(\n    ARM64_NT_CONTEXT* context) noexcept {\n    WriteWindowsNceV4Breadcrumb(\"GUEST_STACK_BRIDGE_REACHED\");\n    if (context == nullptr) {\n        WriteWindowsNceV4Breadcrumb(\"GUEST_CONTEXT_NULL\");\n        std::abort();\n    }\n    WriteWindowsNceV4Breadcrumb(\"BEFORE_GUEST_NTCONTINUE\");\n    WindowsNceTransition::ContinueContext(*context);\n}\n""",
)

replace_once(
    "restore-enter-breadcrumb",
    """extern \"C\" [[noreturn]] void WindowsNceRestoreGuestContext(GuestContext* guest) noexcept {\n    std::fputs(\"IMP008B_E2_RESTORE_ENTER=PASS\\n\", stderr);\n    std::fflush(stderr);\n""",
    """extern \"C\" [[noreturn]] void WindowsNceRestoreGuestContext(GuestContext* guest) noexcept {\n    WriteWindowsNceV4Breadcrumb(\"RESTORE_ENTER\");\n    std::fputs(\"IMP008B_E2_RESTORE_ENTER=PASS\\n\", stderr);\n    std::fflush(stderr);\n""",
)

replace_once(
    "restore-context-match-breadcrumb",
    """    std::fputs(\"IMP008B_E2_RESTORE_CONTEXT_MATCH=PASS\\n\", stderr);\n    std::fflush(stderr);\n\n    parameters->lock.store(SpinLockUnlocked, std::memory_order_release);\n""",
    """    std::fputs(\"IMP008B_E2_RESTORE_CONTEXT_MATCH=PASS\\n\", stderr);\n    std::fflush(stderr);\n    WriteWindowsNceV4Breadcrumb(\"RESTORE_CONTEXT_MATCH\");\n\n    parameters->lock.store(SpinLockUnlocked, std::memory_order_release);\n""",
)

replace_once(
    "stacktop-accepted-breadcrumb",
    """    if (guest->sp <= allocation_base || guest->sp > allocation_end) {\n        std::abort();\n    }\n\n    ARM64_NT_CONTEXT bridge_context = context;\n""",
    """    if (guest->sp <= allocation_base || guest->sp > allocation_end) {\n        WriteWindowsNceV4Breadcrumb(\"STACKTOP_REJECTED\");\n        std::abort();\n    }\n    WriteWindowsNceV4Breadcrumb(\"STACKTOP_ACCEPTED\");\n\n    ARM64_NT_CONTEXT bridge_context = context;\n""",
)

replace_once(
    "before-bridge-ntcontinue-breadcrumb",
    """    bridge_context.X[1] = static_cast<std::uint64_t>(allocation_end);\n    bridge_context.X[2] = static_cast<std::uint64_t>(allocation_base);\n    WindowsNceTransition::ContinueContext(bridge_context);\n""",
    """    bridge_context.X[1] = static_cast<std::uint64_t>(allocation_end);\n    bridge_context.X[2] = static_cast<std::uint64_t>(allocation_base);\n    WriteWindowsNceV4Breadcrumb(\"BEFORE_BRIDGE_NTCONTINUE\");\n    WindowsNceTransition::ContinueContext(bridge_context);\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")
print("REALGAME_TRANSITION_BREADCRUMB_V4=PASS")
