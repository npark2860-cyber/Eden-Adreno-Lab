#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v15-guest-window-lease.py <arm_nce_windows.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

needle = """        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n\n        if (m_windows_pending_nce_fault) {\n"""
replacement = """        RestoreHostTebStackBounds(teb_stack_bounds);\n        NCE::CurrentNceContext::Clear();\n\n        // V15: the MEM_PRIVATE replacement is a native-guest execution-window lease, not a\n        // RunThread-epoch lease. As soon as control returns to host code, merge guest writes back\n        // into the section-backed HostMemory view so fault handling and Dynarmic fallback observe\n        // exactly the same bytes. The next loop iteration reacquires a fresh private lease before\n        // native guest execution resumes.\n        if (private_stack_lease.has_value()) {\n            const u64 v15_restore_pc = m_guest_ctx.pc;\n            const u64 v15_restore_sp = m_guest_ctx.sp;\n            if (!private_stack_lease->Restore()) {\n                LOG_ERROR(Core_ARM, \"V15 failed to restore Windows NCE guest-window stack lease\");\n                hr = HaltReason::PrefetchAbort;\n                break;\n            }\n            private_stack_lease.reset();\n\n            static thread_local bool v15_restore_logged = false;\n            if (!v15_restore_logged) {\n                LOG_INFO(Core_ARM,\n                         \"NCE_V15_GUEST_WINDOW_LEASE_RESTORED pc={:#018x} sp={:#018x}\",\n                         v15_restore_pc, v15_restore_sp);\n                v15_restore_logged = true;\n            }\n        }\n\n        if (m_windows_pending_nce_fault) {\n"""

if text.count(needle) != 1:
    raise SystemExit(f"expected exactly one guest-return seam, found {text.count(needle)}")
text = text.replace(needle, replacement, 1)

old_comment = """    // The private replacement belongs to the complete RunThread epoch. Internal NCE fault/retry\n    // iterations reuse it; restore the section-backed mapping exactly once when the epoch exits.\n"""
new_comment = """    // Safety cleanup only: the normal V15 path restores and resets the private lease immediately\n    // after every native guest window. This catches early exits that occur before that return seam.\n"""
if text.count(old_comment) != 1:
    raise SystemExit(f"expected exactly one epoch-lifetime comment, found {text.count(old_comment)}")
text = text.replace(old_comment, new_comment, 1)

if "NCE_V15_GUEST_WINDOW_LEASE_RESTORED" not in text:
    raise SystemExit("V15 marker missing after transform")

path.write_text(text, encoding="utf-8")
print("REALGAME_V15_GUEST_WINDOW_LEASE=PASS")
