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
    "early-breadcrumb-helper",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsNceFaultTelemetry {\n""",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nconstexpr char WindowsNceV5EarlyBreadcrumbFileName[] = \"eden_nce_v5_early.log\";\n\nvoid WriteWindowsNceV5BreadcrumbToPath(const char* path, const char* marker) noexcept {\n    const HANDLE file = CreateFileA(\n        path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,\n        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);\n    if (file == INVALID_HANDLE_VALUE) {\n        return;\n    }\n\n    DWORD written{};\n    const DWORD marker_length = static_cast<DWORD>(lstrlenA(marker));\n    if (marker_length != 0) {\n        WriteFile(file, marker, marker_length, &written, nullptr);\n        static constexpr char Newline[] = \"\\r\\n\";\n        WriteFile(file, Newline, static_cast<DWORD>(sizeof(Newline) - 1), &written, nullptr);\n        FlushFileBuffers(file);\n    }\n    CloseHandle(file);\n}\n\nvoid WriteWindowsNceV5EarlyBreadcrumb(const char* marker) noexcept {\n    // Sink 1: current working directory. This does not depend on TEMP resolution.\n    WriteWindowsNceV5BreadcrumbToPath(WindowsNceV5EarlyBreadcrumbFileName, marker);\n\n    // Sink 2: normal Windows TEMP directory. Keep this independent so either sink can classify.\n    char temp_path[MAX_PATH]{};\n    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);\n    if (temp_length == 0 || temp_length >= MAX_PATH ||\n        temp_length + sizeof(WindowsNceV5EarlyBreadcrumbFileName) > MAX_PATH) {\n        return;\n    }\n    for (DWORD i = 0; i < sizeof(WindowsNceV5EarlyBreadcrumbFileName); ++i) {\n        temp_path[temp_length + i] = WindowsNceV5EarlyBreadcrumbFileName[i];\n    }\n    WriteWindowsNceV5BreadcrumbToPath(temp_path, marker);\n}\n\nstruct WindowsNceFaultTelemetry {\n""",
)

replace_once(
    "constructor-marker",
    """ArmNce::ArmNce(System& system, bool uses_wall_clock, std::size_t core_index)\n    : ArmInterface{uses_wall_clock}, m_system{system}, m_core_index{core_index},\n      m_windows_break{std::make_unique<NCE::WindowsCrossThreadBreak>()} {\n    m_guest_ctx.system = &m_system;\n}\n""",
    """ArmNce::ArmNce(System& system, bool uses_wall_clock, std::size_t core_index)\n    : ArmInterface{uses_wall_clock}, m_system{system}, m_core_index{core_index},\n      m_windows_break{std::make_unique<NCE::WindowsCrossThreadBreak>()} {\n    WriteWindowsNceV5EarlyBreadcrumb(\"ARMNCE_CONSTRUCTOR\");\n    m_guest_ctx.system = &m_system;\n}\n""",
)

replace_once(
    "initialize-marker",
    """void ArmNce::Initialize() {\n    if (m_windows_break != nullptr && !m_windows_break->IsBound()) {\n""",
    """void ArmNce::Initialize() {\n    WriteWindowsNceV5EarlyBreadcrumb(\"INITIALIZE_ENTER\");\n    if (m_windows_break != nullptr && !m_windows_break->IsBound()) {\n""",
)

replace_once(
    "runthread-entry-marker",
    """HaltReason ArmNce::RunThread(Kernel::KThread* thread) {\n    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n    if (True(hr)) {\n        return hr;\n    }\n\n    auto* const thread_params = &thread->GetNativeExecutionParameters();\n""",
    """HaltReason ArmNce::RunThread(Kernel::KThread* thread) {\n    WriteWindowsNceV5EarlyBreadcrumb(\"RUNTHREAD_ENTER\");\n    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n    if (True(hr)) {\n        WriteWindowsNceV5EarlyBreadcrumb(\"RUNTHREAD_EARLY_HALT\");\n        return hr;\n    }\n\n    WriteWindowsNceV5EarlyBreadcrumb(\"RUNTHREAD_ACTIVE\");\n    auto* const thread_params = &thread->GetNativeExecutionParameters();\n""",
)

replace_once(
    "context-install-marker",
    """    for (;;) {\n        NCE::CurrentNceContext::Install(thread_params);\n\n        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            auto& diag_buffer = m_system.DeviceMemory().buffer;\n""",
    """    for (;;) {\n        WriteWindowsNceV5EarlyBreadcrumb(\"BEFORE_CONTEXT_INSTALL\");\n        NCE::CurrentNceContext::Install(thread_params);\n        WriteWindowsNceV5EarlyBreadcrumb(\"AFTER_CONTEXT_INSTALL\");\n\n        WriteWindowsNceV5EarlyBreadcrumb(\"BEFORE_STACK_LEASE\");\n        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            WriteWindowsNceV5EarlyBreadcrumb(\"STACK_LEASE_FAILED\");\n            auto& diag_buffer = m_system.DeviceMemory().buffer;\n""",
)

replace_once(
    "stack-lease-success-marker",
    """            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        if (g_windows_nce_stack_log_count < WindowsNceStackLogLimit) {\n""",
    """            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n        WriteWindowsNceV5EarlyBreadcrumb(\"AFTER_STACK_LEASE\");\n\n        if (g_windows_nce_stack_log_count < WindowsNceStackLogLimit) {\n""",
)

replace_once(
    "teb-install-marker",
    """        WindowsTebStackBounds teb_stack_bounds{};\n        const bool teb_installed = InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds);\n""",
    """        WindowsTebStackBounds teb_stack_bounds{};\n        WriteWindowsNceV5EarlyBreadcrumb(\"BEFORE_TEB_INSTALL\");\n        const bool teb_installed = InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds);\n        WriteWindowsNceV5EarlyBreadcrumb(teb_installed ? \"AFTER_TEB_INSTALL\" : \"TEB_INSTALL_FAILED\");\n""",
)

replace_once(
    "guest-entry-marker",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            WriteWindowsNceV5EarlyBreadcrumb(\"BEFORE_ENTER_GUEST_POST\");\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            WriteWindowsNceV5EarlyBreadcrumb(\"BEFORE_ENTER_GUEST_CONTEXT\");\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n        WriteWindowsNceV5EarlyBreadcrumb(\"ENTER_GUEST_RETURNED\");\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")
print("REALGAME_EARLY_BREADCRUMB_V5=PASS")
