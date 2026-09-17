#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v28-arm-early-breadcrumb.py <arm_nce_windows.cpp>")

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
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nstruct WindowsTebStackBounds {\n""",
    """std::once_flag g_windows_veh_once;\nPVOID g_windows_veh_handle{};\n\nconstexpr char WindowsNceV28BreadcrumbFileName[] = \"eden_nce_v28_early.log\";\n\nvoid WriteWindowsNceV28BreadcrumbToPath(const char* path, const char* marker) noexcept {\n    const HANDLE file = CreateFileA(\n        path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,\n        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH, nullptr);\n    if (file == INVALID_HANDLE_VALUE) {\n        return;\n    }\n    DWORD written{};\n    const DWORD marker_length = static_cast<DWORD>(lstrlenA(marker));\n    if (marker_length != 0) {\n        WriteFile(file, marker, marker_length, &written, nullptr);\n        static constexpr char Newline[] = \"\\r\\n\";\n        WriteFile(file, Newline, static_cast<DWORD>(sizeof(Newline) - 1), &written, nullptr);\n        FlushFileBuffers(file);\n    }\n    CloseHandle(file);\n}\n\nvoid WriteWindowsNceV28ArmBreadcrumb(const char* marker) noexcept {\n    WriteWindowsNceV28BreadcrumbToPath(WindowsNceV28BreadcrumbFileName, marker);\n    char temp_path[MAX_PATH]{};\n    const DWORD temp_length = GetTempPathA(MAX_PATH, temp_path);\n    if (temp_length == 0 || temp_length >= MAX_PATH ||\n        temp_length + sizeof(WindowsNceV28BreadcrumbFileName) > MAX_PATH) {\n        return;\n    }\n    for (DWORD i = 0; i < sizeof(WindowsNceV28BreadcrumbFileName); ++i) {\n        temp_path[temp_length + i] = WindowsNceV28BreadcrumbFileName[i];\n    }\n    WriteWindowsNceV28BreadcrumbToPath(temp_path, marker);\n}\n\nstruct WindowsTebStackBounds {\n""",
)

replace_once(
    "runthread-entry",
    """HaltReason ArmNce::RunThread(Kernel::KThread* thread) {\n    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n""",
    """HaltReason ArmNce::RunThread(Kernel::KThread* thread) {\n    WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_RUNTHREAD_ENTER\");\n    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n""",
)

replace_once(
    "loop-stack-lease",
    """    for (;;) {\n        NCE::CurrentNceContext::Install(thread_params);\n\n        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n""",
    """    for (;;) {\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_CONTEXT_INSTALL\");\n        NCE::CurrentNceContext::Install(thread_params);\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_AFTER_CONTEXT_INSTALL\");\n\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_STACK_LEASE\");\n        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_STACK_LEASE_FAILED\");\n""",
)

replace_once(
    "stack-lease-success-teb",
    """            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        WindowsTebStackBounds teb_stack_bounds{};\n        if (!InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds)) {\n""",
    """            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_AFTER_STACK_LEASE\");\n\n        WindowsTebStackBounds teb_stack_bounds{};\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_TEB_INSTALL\");\n        if (!InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds)) {\n            WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_TEB_INSTALL_FAILED\");\n""",
)

replace_once(
    "teb-success-guest-entry",
    """            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n""",
    """            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_AFTER_TEB_INSTALL\");\n\n        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_ENTER_GUEST_POST\");\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_ENTER_GUEST_CONTEXT\");\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_ENTER_GUEST_RETURNED\");\n\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_TEB_RESTORE\");\n        RestoreHostTebStackBounds(teb_stack_bounds);\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_AFTER_TEB_RESTORE\");\n        NCE::CurrentNceContext::Clear();\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_AFTER_CONTEXT_CLEAR\");\n""",
)

replace_once(
    "pending-fault",
    """        if (m_windows_pending_nce_fault) {\n""",
    """        if (m_windows_pending_nce_fault) {\n            WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_PENDING_NCE_FAULT\");\n""",
)

replace_once(
    "fallback-dispatch",
    """        const auto fallback = m_windows_x18_runner->Dispatch(\n            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);\n""",
    """        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_FALLBACK_DISPATCH\");\n        const auto fallback = m_windows_x18_runner->Dispatch(\n            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_AFTER_FALLBACK_DISPATCH\");\n""",
)

replace_once(
    "lease-restore",
    """    if (private_stack_lease.has_value() && !private_stack_lease->Restore()) {\n""",
    """    WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_BEFORE_LEASE_RESTORE\");\n    if (private_stack_lease.has_value() && !private_stack_lease->Restore()) {\n        WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_LEASE_RESTORE_FAILED\");\n""",
)

replace_once(
    "runthread-return",
    """    m_guest_ctx.tpidr_el0 = final_tpidr_el0;\n\n    return hr;\n}\n""",
    """    m_guest_ctx.tpidr_el0 = final_tpidr_el0;\n    WriteWindowsNceV28ArmBreadcrumb(\"V28_ARM_RUNTHREAD_RETURN\");\n\n    return hr;\n}\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")

updated = path.read_text(encoding="utf-8")
for marker in [
    "V28_ARM_RUNTHREAD_ENTER",
    "V28_ARM_AFTER_STACK_LEASE",
    "V28_ARM_AFTER_TEB_INSTALL",
    "V28_ARM_BEFORE_ENTER_GUEST_CONTEXT",
    "V28_ARM_ENTER_GUEST_RETURNED",
    "V28_ARM_RUNTHREAD_RETURN",
]:
    if marker not in updated:
        raise SystemExit(f"missing V28 arm marker: {marker}")

print("REALGAME_V28_ARM_BREADCRUMB=PASS")
