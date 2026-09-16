#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: v19-restore-tracker-seam.py <host_memory.cpp> <host_memory_windows_lease.h>")

host_path = Path(sys.argv[1])
lease_path = Path(sys.argv[2])


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


host = host_path.read_text(encoding="utf-8")
host = replace_once(
    host,
    "map-tracker-boundary",
    """        if (!IsNiechePlaceholder(virtual_offset, length)) {\n            Split(virtual_offset, length);\n        }\n        ASSERT(placeholders.find({virtual_offset, virtual_offset + length}) == placeholders.end());\n        TrackPlaceholder(virtual_offset, host_offset, length);\n\n        const DWORD protection = GetWindowsProtection(perms);\n        MapView(virtual_offset, host_offset, length, protection);\n""",
    """        MEMORY_BASIC_INFORMATION v19_before{};\n        auto* const v19_address = virtual_base + virtual_offset;\n        const SIZE_T v19_queried = VirtualQuery(v19_address, &v19_before, sizeof(v19_before));\n        const bool v19_exact_reserved =\n            v19_queried != 0 && v19_before.State == MEM_RESERVE &&\n            v19_before.BaseAddress == v19_address &&\n            static_cast<size_t>(v19_before.RegionSize) == length;\n\n        if (!IsNiechePlaceholder(virtual_offset, length)) {\n            Split(virtual_offset, length);\n        }\n        if (v19_exact_reserved) {\n            LOG_INFO(HW_Memory,\n                     \"NCE_V19_MAP_AFTER_SPLIT addr={:#018x} length={:#x} host_offset={:#x}\",\n                     reinterpret_cast<std::uintptr_t>(v19_address), length, host_offset);\n        }\n\n        const auto v19_tracker = placeholders.find({virtual_offset, virtual_offset + length});\n        if (v19_tracker != placeholders.end()) {\n            LOG_CRITICAL(HW_Memory,\n                         \"NCE_V19_TRACKER_OVERLAP addr={:#018x} length={:#x} tracked_begin={:#x} tracked_end={:#x}\",\n                         reinterpret_cast<std::uintptr_t>(v19_address), length,\n                         v19_tracker->lower(), v19_tracker->upper());\n        }\n        ASSERT(v19_tracker == placeholders.end());\n        TrackPlaceholder(virtual_offset, host_offset, length);\n        if (v19_exact_reserved) {\n            LOG_INFO(HW_Memory,\n                     \"NCE_V19_MAP_AFTER_TRACK addr={:#018x} length={:#x}\",\n                     reinterpret_cast<std::uintptr_t>(v19_address), length);\n        }\n\n        const DWORD protection = GetWindowsProtection(perms);\n        MapView(virtual_offset, host_offset, length, protection);\n        if (v19_exact_reserved) {\n            LOG_INFO(HW_Memory,\n                     \"NCE_V19_MAP_AFTER_MAPVIEW addr={:#018x} length={:#x}\",\n                     reinterpret_cast<std::uintptr_t>(v19_address), length);\n        }\n""",
)
host_path.write_text(host, encoding="utf-8", newline="\n")

lease = lease_path.read_text(encoding="utf-8")
lease = replace_once(
    lease,
    "restore-seam",
    """inline bool HostMemory::PrivateMappingLease::Restore() noexcept {\n    if (!active) {\n        return true;\n    }\n    if (owner == nullptr || virtual_address == nullptr || length == 0) {\n        active = false;\n        return false;\n    }\n\n    std::memcpy(owner->BackingBasePointer() + host_offset, virtual_address, length);\n\n    if (!VirtualFreeEx(GetCurrentProcess(), virtual_address, length,\n                       MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {\n        LOG_ERROR(HW_Memory, \"Failed to return private HostMemory lease to placeholder: {}\",\n                  GetLastError());\n        return false;\n    }\n\n    active = false;\n    owner->Map(reinterpret_cast<size_t>(virtual_address), host_offset, length, perms, false);\n\n    MEMORY_BASIC_INFORMATION restored{};\n""",
    """inline bool HostMemory::PrivateMappingLease::Restore() noexcept {\n    if (!active) {\n        return true;\n    }\n    if (owner == nullptr || virtual_address == nullptr || length == 0) {\n        active = false;\n        return false;\n    }\n\n    LOG_INFO(HW_Memory,\n             \"NCE_V19_RESTORE_ENTER addr={:#018x} length={:#x} host_offset={:#x}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address), length, host_offset);\n    std::memcpy(owner->BackingBasePointer() + host_offset, virtual_address, length);\n    LOG_INFO(HW_Memory,\n             \"NCE_V19_RESTORE_AFTER_SYNC addr={:#018x} length={:#x}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address), length);\n\n    if (!VirtualFreeEx(GetCurrentProcess(), virtual_address, length,\n                       MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {\n        LOG_ERROR(HW_Memory, \"Failed to return private HostMemory lease to placeholder: {}\",\n                  GetLastError());\n        return false;\n    }\n    LOG_INFO(HW_Memory,\n             \"NCE_V19_RESTORE_PLACEHOLDER_READY addr={:#018x} length={:#x}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address), length);\n\n    active = false;\n    LOG_INFO(HW_Memory,\n             \"NCE_V19_RESTORE_MAP_BEGIN addr={:#018x} length={:#x} host_offset={:#x}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address), length, host_offset);\n    owner->Map(reinterpret_cast<size_t>(virtual_address), host_offset, length, perms, false);\n    LOG_INFO(HW_Memory,\n             \"NCE_V19_RESTORE_MAP_END addr={:#018x} length={:#x}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address), length);\n\n    MEMORY_BASIC_INFORMATION restored{};\n""",
)
lease = replace_once(
    lease,
    "restore-verify",
    """    const bool restored_mapped =\n        VirtualQuery(virtual_address, &restored, sizeof(restored)) != 0 &&\n        restored.Type == MEM_MAPPED;\n    if (!restored_mapped) {\n""",
    """    const SIZE_T v19_restored_query = VirtualQuery(virtual_address, &restored, sizeof(restored));\n    const bool restored_mapped = v19_restored_query != 0 && restored.Type == MEM_MAPPED;\n    LOG_INFO(HW_Memory,\n             \"NCE_V19_RESTORE_VERIFY addr={:#018x} length={:#x} query={} state={:#x} type={:#x} region_size={:#x} mapped={}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address), length, v19_restored_query,\n             v19_restored_query != 0 ? static_cast<unsigned long>(restored.State) : 0UL,\n             v19_restored_query != 0 ? static_cast<unsigned long>(restored.Type) : 0UL,\n             v19_restored_query != 0 ? static_cast<size_t>(restored.RegionSize) : 0ULL,\n             restored_mapped);\n    if (!restored_mapped) {\n""",
)
lease_path.write_text(lease, encoding="utf-8", newline="\n")

for p, marker in [
    (host_path, "NCE_V19_TRACKER_OVERLAP"),
    (host_path, "NCE_V19_MAP_AFTER_MAPVIEW"),
    (lease_path, "NCE_V19_RESTORE_PLACEHOLDER_READY"),
    (lease_path, "NCE_V19_RESTORE_VERIFY"),
]:
    if marker not in p.read_text(encoding="utf-8"):
        raise SystemExit(f"V19 marker missing from {p}: {marker}")

print("REALGAME_V19_RESTORE_TRACKER_SEAM=PASS")