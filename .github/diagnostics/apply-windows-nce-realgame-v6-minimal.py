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
    "stacktop-equality-arm",
    """    if (guest_sp_value <= allocation_base || guest_sp_value >= allocation_end) {\n""",
    """    if (guest_sp_value <= allocation_base || guest_sp_value > allocation_end) {\n""",
)

replace_once(
    "v6-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nconstexpr char WindowsNceV6BreadcrumbFileName[] = \"eden_nce_v6_minimal.log\";\n\nvoid WriteWindowsNceV6BreadcrumbToPath(const char* path, const char* marker) noexcept {\n    const HANDLE file = CreateFileA(\n        path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,\n        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);\n    if (file == INVALID_HANDLE_VALUE) {\n        return;\n    }\n\n    DWORD written{};\n    const DWORD marker_length = static_cast<DWORD>(lstrlenA(marker));\n    if (marker_length != 0) {\n        WriteFile(file, marker, marker_length, &written, nullptr);\n        static constexpr char Newline[] = \"\\r\\n\";\n        WriteFile(file, Newline, static_cast<DWORD>(sizeof(Newline) - 1), &written, nullptr);\n        FlushFileBuffers(file);\n    }\n    CloseHandle(file);\n}\n\nvoid WriteWindowsNceV6Breadcrumb(const char* marker) noexcept {\n    WriteWindowsNceV6BreadcrumbToPath(WindowsNceV6BreadcrumbFileName, marker);\n\n    char temp_path[MAX_PATH]{};\n    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);\n    if (temp_length == 0 || temp_length >= MAX_PATH ||\n        temp_length + sizeof(WindowsNceV6BreadcrumbFileName) > MAX_PATH) {\n        return;\n    }\n    for (DWORD i = 0; i < sizeof(WindowsNceV6BreadcrumbFileName); ++i) {\n        temp_path[temp_length + i] = WindowsNceV6BreadcrumbFileName[i];\n    }\n    WriteWindowsNceV6BreadcrumbToPath(temp_path, marker);\n}\n\nstruct WindowsTebStackBounds {\n""",
)

replace_once(
    "constructor-marker",
    """ArmNce::ArmNce(System& system, bool uses_wall_clock, std::size_t core_index)\n    : ArmInterface{uses_wall_clock}, m_system{system}, m_core_index{core_index},\n      m_windows_break{std::make_unique<NCE::WindowsCrossThreadBreak>()} {\n    m_guest_ctx.system = &m_system;\n}\n""",
    """ArmNce::ArmNce(System& system, bool uses_wall_clock, std::size_t core_index)\n    : ArmInterface{uses_wall_clock}, m_system{system}, m_core_index{core_index},\n      m_windows_break{std::make_unique<NCE::WindowsCrossThreadBreak>()} {\n    WriteWindowsNceV6Breadcrumb(\"ARMNCE_CONSTRUCTOR\");\n    m_guest_ctx.system = &m_system;\n}\n""",
)

replace_once(
    "initialize-marker",
    """void ArmNce::Initialize() {\n    if (m_windows_break != nullptr && !m_windows_break->IsBound()) {\n""",
    """void ArmNce::Initialize() {\n    WriteWindowsNceV6Breadcrumb(\"INITIALIZE_ENTER\");\n    if (m_windows_break != nullptr && !m_windows_break->IsBound()) {\n""",
)

replace_once(
    "runthread-entry-marker",
    """HaltReason ArmNce::RunThread(Kernel::KThread* thread) {\n    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n    if (True(hr)) {\n        return hr;\n    }\n\n    auto* const thread_params = &thread->GetNativeExecutionParameters();\n""",
    """HaltReason ArmNce::RunThread(Kernel::KThread* thread) {\n    WriteWindowsNceV6Breadcrumb(\"RUNTHREAD_ENTER\");\n    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n    if (True(hr)) {\n        WriteWindowsNceV6Breadcrumb(\"RUNTHREAD_EARLY_HALT\");\n        return hr;\n    }\n\n    WriteWindowsNceV6Breadcrumb(\"RUNTHREAD_ACTIVE\");\n    auto* const thread_params = &thread->GetNativeExecutionParameters();\n""",
)

replace_once(
    "loop-context-stack-markers",
    """    for (;;) {\n        NCE::CurrentNceContext::Install(thread_params);\n\n        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        WindowsTebStackBounds teb_stack_bounds{};\n        if (!InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds)) {\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n""",
    """    for (;;) {\n        WriteWindowsNceV6Breadcrumb(\"BEFORE_CONTEXT_INSTALL\");\n        NCE::CurrentNceContext::Install(thread_params);\n        WriteWindowsNceV6Breadcrumb(\"AFTER_CONTEXT_INSTALL\");\n\n        WriteWindowsNceV6Breadcrumb(\"BEFORE_STACK_LEASE\");\n        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            WriteWindowsNceV6Breadcrumb(\"STACK_LEASE_FAILED\");\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n        WriteWindowsNceV6Breadcrumb(\"AFTER_STACK_LEASE\");\n\n        WindowsTebStackBounds teb_stack_bounds{};\n        WriteWindowsNceV6Breadcrumb(\"BEFORE_TEB_INSTALL\");\n        if (!InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds)) {\n            WriteWindowsNceV6Breadcrumb(\"TEB_INSTALL_FAILED\");\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n        WriteWindowsNceV6Breadcrumb(\"AFTER_TEB_INSTALL\");\n\n        WriteWindowsNceV6Breadcrumb(\"BEFORE_POST_HANDLER_LOOKUP\");\n        const auto it = post_handlers.find(m_guest_ctx.pc);\n        WriteWindowsNceV6Breadcrumb(\"AFTER_POST_HANDLER_LOOKUP\");\n        if (it != post_handlers.end()) {\n            WriteWindowsNceV6Breadcrumb(\"BEFORE_ENTER_GUEST_POST\");\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            WriteWindowsNceV6Breadcrumb(\"BEFORE_ENTER_GUEST_CONTEXT\");\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n        WriteWindowsNceV6Breadcrumb(\"ENTER_GUEST_RETURNED\");\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        WriteWindowsNceV6Breadcrumb(\"HOST_TEB_RESTORED\");\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")
print("REALGAME_V6_MINIMAL=PASS")
