#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v24-prefetch-source.py <arm_nce_windows.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


text = replace_once(
    text,
    "entry-prefetch",
    """    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n    if (True(hr)) {\n        return hr;\n    }\n""",
    """    HaltReason hr = static_cast<HaltReason>(m_guest_ctx.esr_el1.exchange(0));\n    if (True(hr)) {\n        if (True(hr & HaltReason::PrefetchAbort)) {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=entry_esr hr=0x{:016X} pc={:#018x} sp={:#018x}\",\n                      static_cast<u64>(hr), m_guest_ctx.pc, m_guest_ctx.sp);\n        }\n        return hr;\n    }\n""",
)

text = replace_once(
    text,
    "stack-lease-prefetch",
    """        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
    """        if (!EnsureWindowsGuestStackLease(m_system, process, m_guest_ctx.sp,\n                                          private_stack_lease)) {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=stack_lease pc={:#018x} sp={:#018x}\",\n                      m_guest_ctx.pc, m_guest_ctx.sp);\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
)

text = replace_once(
    text,
    "teb-prefetch",
    """        WindowsTebStackBounds teb_stack_bounds{};\n        if (!InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds)) {\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
    """        WindowsTebStackBounds teb_stack_bounds{};\n        if (!InstallGuestTebStackBounds(m_guest_ctx.sp, teb_stack_bounds)) {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=teb_bounds pc={:#018x} sp={:#018x}\",\n                      m_guest_ctx.pc, m_guest_ctx.sp);\n            NCE::CurrentNceContext::Clear();\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
)

text = replace_once(
    text,
    "guest-return-prefetch",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n""",
    """        if (const auto it = post_handlers.find(m_guest_ctx.pc); it != post_handlers.end()) {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuest(\n                &m_guest_ctx, reinterpret_cast<const void*>(it->second)));\n        } else {\n            hr = static_cast<HaltReason>(NCE::WindowsNceEnterGuestContext(&m_guest_ctx));\n        }\n\n        if (True(hr & HaltReason::PrefetchAbort) || m_windows_pending_nce_fault) {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=guest_return hr=0x{:016X} pending={} pc={:#018x} sp={:#018x} fault={:#018x} page={:#018x}\",\n                      static_cast<u64>(hr), m_windows_pending_nce_fault, m_guest_ctx.pc,\n                      m_guest_ctx.sp, m_windows_pending_nce_fault_address,\n                      m_windows_pending_nce_fault_page);\n        }\n\n        RestoreHostTebStackBounds(teb_stack_bounds);\n""",
)

text = replace_once(
    text,
    "unhandled-execute-av",
    """            if (m_guest_ctx.pc != pending_fault_address) {\n                m_guest_ctx.pc += sizeof(u32);\n                continue;\n            }\n\n            hr = HaltReason::PrefetchAbort;\n            break;\n""",
    """            if (m_guest_ctx.pc != pending_fault_address) {\n                m_guest_ctx.pc += sizeof(u32);\n                continue;\n            }\n\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=unhandled_execute_av pc={:#018x} sp={:#018x} fault={:#018x} page={:#018x}\",\n                      m_guest_ctx.pc, m_guest_ctx.sp, pending_fault_address, pending_fault_page);\n            hr = HaltReason::PrefetchAbort;\n            break;\n""",
)

text = replace_once(
    text,
    "v16-sync-to-prefetch",
    """        if (private_stack_lease.has_value() && !private_stack_lease->SyncToBacking()) {\n            LOG_ERROR(Core_ARM, \"V16 failed to synchronize private NCE stack to backing\");\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
    """        if (private_stack_lease.has_value() && !private_stack_lease->SyncToBacking()) {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=v16_sync_to_backing pc={:#018x} sp={:#018x}\",\n                      m_guest_ctx.pc, m_guest_ctx.sp);\n            LOG_ERROR(Core_ARM, \"V16 failed to synchronize private NCE stack to backing\");\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
)

text = replace_once(
    text,
    "v16-sync-from-prefetch",
    """        if (fallback.handled && private_stack_lease.has_value() &&\n            !private_stack_lease->SyncFromBacking()) {\n            LOG_ERROR(Core_ARM, \"V16 failed to synchronize fallback stack writes to private view\");\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
    """        if (fallback.handled && private_stack_lease.has_value() &&\n            !private_stack_lease->SyncFromBacking()) {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V24_PREFETCH_SOURCE source=v16_sync_from_backing pc={:#018x} sp={:#018x}\",\n                      m_guest_ctx.pc, m_guest_ctx.sp);\n            LOG_ERROR(Core_ARM, \"V16 failed to synchronize fallback stack writes to private view\");\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n""",
)

text = replace_once(
    text,
    "fallback-incomplete-prefetch",
    """        if (!fallback.metadata_found || !fallback.step.completed) {\n            hr = fallback.step.halt_reason;\n            if (!True(hr)) {\n                hr = HaltReason::PrefetchAbort;\n            }\n            break;\n        }\n""",
    """        if (!fallback.metadata_found || !fallback.step.completed) {\n            hr = fallback.step.halt_reason;\n            if (!True(hr)) {\n                hr = HaltReason::PrefetchAbort;\n            }\n            if (True(hr & HaltReason::PrefetchAbort)) {\n                LOG_ERROR(Core_ARM,\n                          \"NCE_V24_PREFETCH_SOURCE source=fallback_incomplete metadata_found={} step_completed={} hr=0x{:016X} pc={:#018x} sp={:#018x}\",\n                          fallback.metadata_found, fallback.step.completed, static_cast<u64>(hr),\n                          m_guest_ctx.pc, m_guest_ctx.sp);\n            }\n            break;\n        }\n""",
)

text = replace_once(
    text,
    "fallback-step-prefetch",
    """        if (True(fallback.step.halt_reason)) {\n            hr = fallback.step.halt_reason;\n            break;\n        }\n""",
    """        if (True(fallback.step.halt_reason)) {\n            hr = fallback.step.halt_reason;\n            if (True(hr & HaltReason::PrefetchAbort)) {\n                LOG_ERROR(Core_ARM,\n                          \"NCE_V24_PREFETCH_SOURCE source=fallback_step hr=0x{:016X} pc={:#018x} sp={:#018x}\",\n                          static_cast<u64>(hr), m_guest_ctx.pc, m_guest_ctx.sp);\n            }\n            break;\n        }\n""",
)

text = replace_once(
    text,
    "lease-restore-prefetch",
    """    if (private_stack_lease.has_value() && !private_stack_lease->Restore()) {\n        LOG_ERROR(Core_ARM, \"Failed to restore Windows NCE private stack lease\");\n        hr = HaltReason::PrefetchAbort;\n    }\n""",
    """    if (private_stack_lease.has_value() && !private_stack_lease->Restore()) {\n        LOG_ERROR(Core_ARM,\n                  \"NCE_V24_PREFETCH_SOURCE source=lease_restore pc={:#018x} sp={:#018x}\",\n                  m_guest_ctx.pc, m_guest_ctx.sp);\n        LOG_ERROR(Core_ARM, \"Failed to restore Windows NCE private stack lease\");\n        hr = HaltReason::PrefetchAbort;\n    }\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")

if "NCE_V24_PREFETCH_SOURCE" not in path.read_text(encoding="utf-8"):
    raise SystemExit("V24 marker missing")

print("REALGAME_V24_PREFETCH_SOURCE=PASS")
