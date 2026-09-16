#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("usage: v16-fallback-stack-sync.py <host_memory.h> <host_memory_windows_lease.h> <arm_nce_windows.cpp>")

host_path = Path(sys.argv[1])
lease_path = Path(sys.argv[2])
arm_path = Path(sys.argv[3])


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


host = host_path.read_text(encoding="utf-8")
host = replace_once(
    host,
    "lease-sync-declarations",
    """        [[nodiscard]] bool Restore() noexcept;\n        [[nodiscard]] bool ContainsAddress(u64 address) const noexcept;\n""",
    """        [[nodiscard]] bool Restore() noexcept;\n        [[nodiscard]] bool ContainsAddress(u64 address) const noexcept;\n        [[nodiscard]] bool SyncToBacking() noexcept;\n        [[nodiscard]] bool SyncFromBacking() noexcept;\n""",
)
host_path.write_text(host, encoding="utf-8", newline="\n")

lease = lease_path.read_text(encoding="utf-8")
lease = replace_once(
    lease,
    "lease-sync-definitions",
    """inline bool HostMemory::PrivateMappingLease::Restore() noexcept {\n""",
    """inline bool HostMemory::PrivateMappingLease::SyncToBacking() noexcept {\n    if (!active || owner == nullptr || virtual_address == nullptr || length == 0) {\n        return false;\n    }\n    std::memcpy(owner->BackingBasePointer() + host_offset, virtual_address, length);\n    std::atomic_thread_fence(std::memory_order_release);\n    return true;\n}\n\ninline bool HostMemory::PrivateMappingLease::SyncFromBacking() noexcept {\n    if (!active || owner == nullptr || virtual_address == nullptr || length == 0) {\n        return false;\n    }\n    std::atomic_thread_fence(std::memory_order_acquire);\n    std::memcpy(virtual_address, owner->BackingBasePointer() + host_offset, length);\n    return true;\n}\n\ninline bool HostMemory::PrivateMappingLease::Restore() noexcept {\n""",
)
lease = replace_once(
    lease,
    "atomic-include",
    """#include <algorithm>\n#include <cstdint>\n""",
    """#include <algorithm>\n#include <atomic>\n#include <cstdint>\n""",
)
lease_path.write_text(lease, encoding="utf-8", newline="\n")

arm = arm_path.read_text(encoding="utf-8")
arm = replace_once(
    arm,
    "fallback-coherence-boundary",
    """        const auto fallback = m_windows_x18_runner->Dispatch(\n            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);\n        if (!fallback.handled) {\n            break;\n        }\n""",
    """        // V16: while the native guest stack is temporarily MEM_PRIVATE, Dynarmic fallback\n        // still observes Core::Memory's section-backed storage. Synchronize the complete leased\n        // stack at this engine boundary so both execution engines observe one coherent guest state\n        // without tearing down/recreating the Windows mapping for every fallback instruction.\n        if (private_stack_lease.has_value() && !private_stack_lease->SyncToBacking()) {\n            LOG_ERROR(Core_ARM, \"V16 failed to synchronize private NCE stack to backing\");\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        const auto fallback = m_windows_x18_runner->Dispatch(\n            static_cast<u64>(hr), thread, m_guest_ctx, post_handlers);\n\n        if (fallback.handled && private_stack_lease.has_value() &&\n            !private_stack_lease->SyncFromBacking()) {\n            LOG_ERROR(Core_ARM, \"V16 failed to synchronize fallback stack writes to private view\");\n            hr = HaltReason::PrefetchAbort;\n            break;\n        }\n\n        if (fallback.handled && private_stack_lease.has_value()) {\n            static thread_local bool v16_sync_logged = false;\n            if (!v16_sync_logged) {\n                LOG_INFO(Core_ARM,\n                         \"NCE_V16_FALLBACK_STACK_SYNC pc={:#018x} sp={:#018x}\",\n                         m_guest_ctx.pc, m_guest_ctx.sp);\n                v16_sync_logged = true;\n            }\n        }\n\n        if (!fallback.handled) {\n            break;\n        }\n""",
)
arm_path.write_text(arm, encoding="utf-8", newline="\n")

for p, marker in [
    (host_path, "SyncToBacking"),
    (lease_path, "SyncFromBacking"),
    (arm_path, "NCE_V16_FALLBACK_STACK_SYNC"),
]:
    if marker not in p.read_text(encoding="utf-8"):
        raise SystemExit(f"V16 marker missing from {p}")

print("REALGAME_V16_FALLBACK_STACK_SYNC=PASS")
