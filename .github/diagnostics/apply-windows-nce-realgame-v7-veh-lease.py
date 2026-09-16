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
    "veh-entry-and-no-guest",
    """LONG CALLBACK WindowsNceVectoredExceptionHandler(PEXCEPTION_POINTERS exception) noexcept {\n    if (exception == nullptr || exception->ExceptionRecord == nullptr ||\n        exception->ContextRecord == nullptr) {\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n\n    auto* const guest = NCE::WindowsExceptionContext::CurrentGuestContext();\n    if (guest == nullptr || guest->parent == nullptr || guest->parent->m_running_thread == nullptr) {\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n\n    auto* const nce = guest->parent;\n""",
    """LONG CALLBACK WindowsNceVectoredExceptionHandler(PEXCEPTION_POINTERS exception) noexcept {\n    if (exception == nullptr || exception->ExceptionRecord == nullptr ||\n        exception->ContextRecord == nullptr) {\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n    WriteWindowsNceV6Breadcrumb(\"V7_VEH_ENTER\");\n\n    auto* const guest = NCE::WindowsExceptionContext::CurrentGuestContext();\n    if (guest == nullptr || guest->parent == nullptr || guest->parent->m_running_thread == nullptr) {\n        WriteWindowsNceV6Breadcrumb(\"V7_VEH_NO_GUEST_CHAIN\");\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n    WriteWindowsNceV6Breadcrumb(\"V7_VEH_GUEST_OWNED\");\n\n    auto* const nce = guest->parent;\n""",
)

replace_once(
    "veh-host-stack",
    """    if (nce->m_windows_break != nullptr && nce->m_windows_break->IsHostStackPointer(context.Sp)) {\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
    """    if (nce->m_windows_break != nullptr && nce->m_windows_break->IsHostStackPointer(context.Sp)) {\n        WriteWindowsNceV6Breadcrumb(\"V7_VEH_HOST_STACK_CHAIN\");\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
)

replace_once(
    "veh-x18",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&\n        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(\n            context.Pc, process->GetPostHandlers()).has_value()) {\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(\n            exception, *guest, process->GetPostHandlers());\n        if (redirected) {\n            return EXCEPTION_CONTINUE_EXECUTION;\n        }\n        params->lock.store(SpinLockUnlocked, std::memory_order_release);\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&\n        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(\n            context.Pc, process->GetPostHandlers()).has_value()) {\n        WriteWindowsNceV6Breadcrumb(\"V7_VEH_X18_BREAKPOINT\");\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(\n            exception, *guest, process->GetPostHandlers());\n        if (redirected) {\n            WriteWindowsNceV6Breadcrumb(\"V7_VEH_X18_REDIRECTED\");\n            return EXCEPTION_CONTINUE_EXECUTION;\n        }\n        WriteWindowsNceV6Breadcrumb(\"V7_VEH_X18_CHAIN\");\n        params->lock.store(SpinLockUnlocked, std::memory_order_release);\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
)

replace_once(
    "veh-av-and-unknown",
    """    if (NCE::WindowsExceptionContext::IsAccessViolation(*exception->ExceptionRecord)) {\n        const auto fault_address = reinterpret_cast<u64>(\n            NCE::WindowsExceptionContext::GetFaultAddress(*exception->ExceptionRecord));\n        nce->m_windows_pending_nce_fault = true;\n        nce->m_windows_pending_nce_fault_address = fault_address;\n        nce->m_windows_pending_nce_fault_page = fault_address & ~Memory::YUZU_PAGEMASK;\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        NCE::WindowsNceTransition::RedirectToHost(\n            context, *guest, true, static_cast<u64>(HaltReason::PrefetchAbort));\n        return EXCEPTION_CONTINUE_EXECUTION;\n    }\n\n    // IMP-008A does not claim complete game fault compatibility. Unknown host/guest exception\n    // classes remain chainable instead of being swallowed by the NCE VEH.\n    return EXCEPTION_CONTINUE_SEARCH;\n""",
    """    if (NCE::WindowsExceptionContext::IsAccessViolation(*exception->ExceptionRecord)) {\n        WriteWindowsNceV6Breadcrumb(\"V7_VEH_ACCESS_VIOLATION\");\n        const auto fault_address = reinterpret_cast<u64>(\n            NCE::WindowsExceptionContext::GetFaultAddress(*exception->ExceptionRecord));\n        nce->m_windows_pending_nce_fault = true;\n        nce->m_windows_pending_nce_fault_address = fault_address;\n        nce->m_windows_pending_nce_fault_page = fault_address & ~Memory::YUZU_PAGEMASK;\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        WriteWindowsNceV6Breadcrumb(\"V7_VEH_AV_REDIRECT_HOST\");\n        NCE::WindowsNceTransition::RedirectToHost(\n            context, *guest, true, static_cast<u64>(HaltReason::PrefetchAbort));\n        return EXCEPTION_CONTINUE_EXECUTION;\n    }\n\n    // IMP-008A does not claim complete game fault compatibility. Unknown host/guest exception\n    // classes remain chainable instead of being swallowed by the NCE VEH.\n    WriteWindowsNceV6Breadcrumb(\"V7_VEH_UNKNOWN_CHAIN\");\n    return EXCEPTION_CONTINUE_SEARCH;\n""",
)

replace_once(
    "lease-restore-boundary",
    """    if (private_stack_lease.has_value() && !private_stack_lease->Restore()) {\n        LOG_ERROR(Core_ARM, \"Failed to restore Windows NCE private stack lease\");\n        hr = HaltReason::PrefetchAbort;\n    }\n""",
    """    if (private_stack_lease.has_value()) {\n        WriteWindowsNceV6Breadcrumb(\"V7_BEFORE_LEASE_RESTORE\");\n        const bool lease_restored = private_stack_lease->Restore();\n        WriteWindowsNceV6Breadcrumb(lease_restored ? \"V7_AFTER_LEASE_RESTORE_OK\"\n                                                   : \"V7_AFTER_LEASE_RESTORE_FAIL\");\n        if (!lease_restored) {\n            LOG_ERROR(Core_ARM, \"Failed to restore Windows NCE private stack lease\");\n            hr = HaltReason::PrefetchAbort;\n        }\n    } else {\n        WriteWindowsNceV6Breadcrumb(\"V7_NO_LEASE_RESTORE\");\n    }\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")
print("REALGAME_V7_VEH_LEASE=PASS")
