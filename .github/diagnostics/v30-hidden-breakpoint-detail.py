#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v30-hidden-breakpoint-detail.py <arm_nce_windows.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(label: str, old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    text = text.replace(old, new, 1)


# V30 deliberately starts from V29 telemetry and changes only the hidden-breakpoint visibility.
replace_once(
    "detail-file",
    'constexpr char WindowsNceV29DetailFileName[] = "eden_nce_v29_post_detail.log";',
    'constexpr char WindowsNceV29DetailFileName[] = "eden_nce_v30_breakpoint_detail.log";',
)
text = text.replace('"V29_POST_ENTER ', '"V30_POST_ENTER ')
text = text.replace('"V29_VEH code=', '"V30_VEH code=')

replace_once(
    "breakpoint-detail-helper",
    """struct WindowsTebStackBounds {\n""",
    r'''void WriteWindowsNceV30BreakpointDetail(PEXCEPTION_POINTERS exception,
                                                const NCE::X18FallbackMetadata& metadata,
                                                const char* classification) noexcept {
    if (exception == nullptr || exception->ExceptionRecord == nullptr ||
        exception->ContextRecord == nullptr) {
        return;
    }
    const auto& record = *exception->ExceptionRecord;
    const auto& context = *reinterpret_cast<const ARM64_NT_CONTEXT*>(exception->ContextRecord);
    const auto at_pc = NCE::WindowsX18FallbackTrap::FindOriginalInstruction(context.Pc, metadata);
    const auto at_prev = context.Pc >= sizeof(u32)
                             ? NCE::WindowsX18FallbackTrap::FindOriginalInstruction(
                                   context.Pc - sizeof(u32), metadata)
                             : std::nullopt;
    char line[768]{};
    std::snprintf(
        line, sizeof(line),
        "V30_BREAKPOINT_UNCLAIMED class=%s exception_address=%p ctx_pc=0x%016llX "
        "ctx_sp=0x%016llX metadata_pc=%u original_pc=0x%08X metadata_pc_minus_4=%u "
        "original_pc_minus_4=0x%08X",
        classification, record.ExceptionAddress,
        static_cast<unsigned long long>(context.Pc),
        static_cast<unsigned long long>(context.Sp), at_pc.has_value() ? 1u : 0u,
        at_pc.value_or(0), at_prev.has_value() ? 1u : 0u, at_prev.value_or(0));
    WriteWindowsNceV29Line(line);
}

struct WindowsTebStackBounds {
''',
)

replace_once(
    "breakpoint-claim-path",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT &&\n        NCE::WindowsX18FallbackTrap::FindOriginalInstruction(\n            context.Pc, process->GetPostHandlers()).has_value()) {\n        params->lock.store(SpinLockLocked, std::memory_order_release);\n        const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(\n            exception, *guest, process->GetPostHandlers());\n        if (redirected) {\n            return EXCEPTION_CONTINUE_EXECUTION;\n        }\n        params->lock.store(SpinLockUnlocked, std::memory_order_release);\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
    """    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_BREAKPOINT) {\n        const auto x18_original = NCE::WindowsX18FallbackTrap::FindOriginalInstruction(\n            context.Pc, process->GetPostHandlers());\n        if (x18_original.has_value()) {\n            params->lock.store(SpinLockLocked, std::memory_order_release);\n            const bool redirected = NCE::WindowsX18FallbackTrap::TryRedirect(\n                exception, *guest, process->GetPostHandlers());\n            if (redirected) {\n                return EXCEPTION_CONTINUE_EXECUTION;\n            }\n            params->lock.store(SpinLockUnlocked, std::memory_order_release);\n            WriteWindowsNceV30BreakpointDetail(\n                exception, process->GetPostHandlers(), \"metadata_redirect_failed\");\n            return EXCEPTION_CONTINUE_SEARCH;\n        }\n\n        WriteWindowsNceV30BreakpointDetail(\n            exception, process->GetPostHandlers(), \"no_metadata\");\n        return EXCEPTION_CONTINUE_SEARCH;\n    }\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")
updated = path.read_text(encoding="utf-8")
for marker in [
    "eden_nce_v30_breakpoint_detail.log",
    "V30_POST_ENTER",
    "V30_VEH",
    "V30_BREAKPOINT_UNCLAIMED",
    "metadata_redirect_failed",
    "no_metadata",
]:
    if marker not in updated:
        raise SystemExit(f"missing V30 marker: {marker}")

print("REALGAME_V30_HIDDEN_BREAKPOINT_DETAIL=PASS")
