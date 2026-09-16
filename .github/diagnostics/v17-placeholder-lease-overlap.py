#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: v17-placeholder-lease-overlap.py <host_memory.cpp> <host_memory_windows_lease.h>")

host_cpp_path = Path(sys.argv[1])
lease_path = Path(sys.argv[2])


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


host_cpp = host_cpp_path.read_text(encoding="utf-8")
host_cpp = replace_once(
    host_cpp,
    "split-diagnostic",
    """    void Split(size_t virtual_offset, size_t length) {\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(virtual_base + virtual_offset), length,\n                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {\n            LOG_CRITICAL(HW_Memory, \"Failed to split placeholder\");\n        }\n    }\n""",
    """    void Split(size_t virtual_offset, size_t length) {\n        auto* const address = virtual_base + virtual_offset;\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(address), length,\n                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {\n            const DWORD error = GetLastError();\n            MEMORY_BASIC_INFORMATION mbi{};\n            const SIZE_T queried = VirtualQuery(address, &mbi, sizeof(mbi));\n            LOG_CRITICAL(\n                HW_Memory,\n                \"NCE_V17_SPLIT_FAIL addr={:#018x} offset={:#x} length={:#x} error={} query={} \"\n                \"state={:#x} type={:#x} alloc_base={:#018x} region_base={:#018x} region_size={:#x}\",\n                reinterpret_cast<std::uintptr_t>(address), virtual_offset, length, error, queried,\n                queried != 0 ? static_cast<unsigned long>(mbi.State) : 0UL,\n                queried != 0 ? static_cast<unsigned long>(mbi.Type) : 0UL,\n                queried != 0 ? reinterpret_cast<std::uintptr_t>(mbi.AllocationBase) : 0ULL,\n                queried != 0 ? reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) : 0ULL,\n                queried != 0 ? static_cast<size_t>(mbi.RegionSize) : 0ULL);\n        }\n    }\n""",
)
host_cpp = replace_once(
    host_cpp,
    "coalesce-diagnostic",
    """    void Coalesce(size_t virtual_offset, size_t length) {\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(virtual_base + virtual_offset), length,\n                           MEM_RELEASE | MEM_COALESCE_PLACEHOLDERS)) {\n            LOG_CRITICAL(HW_Memory, \"Failed to coalesce placeholders\");\n        }\n    }\n""",
    """    void Coalesce(size_t virtual_offset, size_t length) {\n        auto* const address = virtual_base + virtual_offset;\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(address), length,\n                           MEM_RELEASE | MEM_COALESCE_PLACEHOLDERS)) {\n            const DWORD error = GetLastError();\n            MEMORY_BASIC_INFORMATION mbi{};\n            const SIZE_T queried = VirtualQuery(address, &mbi, sizeof(mbi));\n            LOG_CRITICAL(\n                HW_Memory,\n                \"NCE_V17_COALESCE_FAIL addr={:#018x} offset={:#x} length={:#x} error={} query={} \"\n                \"state={:#x} type={:#x} alloc_base={:#018x} region_base={:#018x} region_size={:#x}\",\n                reinterpret_cast<std::uintptr_t>(address), virtual_offset, length, error, queried,\n                queried != 0 ? static_cast<unsigned long>(mbi.State) : 0UL,\n                queried != 0 ? static_cast<unsigned long>(mbi.Type) : 0UL,\n                queried != 0 ? reinterpret_cast<std::uintptr_t>(mbi.AllocationBase) : 0ULL,\n                queried != 0 ? reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) : 0ULL,\n                queried != 0 ? static_cast<size_t>(mbi.RegionSize) : 0ULL);\n        }\n    }\n""",
)
host_cpp_path.write_text(host_cpp, encoding="utf-8", newline="\n")

lease = lease_path.read_text(encoding="utf-8")
lease = replace_once(
    lease,
    "lease-range-diagnostic",
    """    return PrivateMappingLease{this, static_cast<u8*>(virtual_address_), host_offset_, length_,\n                               perms_};\n""",
    """    LOG_INFO(HW_Memory,\n             \"NCE_V17_LEASE_RANGE base={:#018x} length={:#x} host_offset={:#x} state={:#x} type={:#x}\",\n             reinterpret_cast<std::uintptr_t>(virtual_address_), length_, host_offset_,\n             static_cast<unsigned long>(private_region.State),\n             static_cast<unsigned long>(private_region.Type));\n\n    return PrivateMappingLease{this, static_cast<u8*>(virtual_address_), host_offset_, length_,\n                               perms_};\n""",
)
lease_path.write_text(lease, encoding="utf-8", newline="\n")

for p, marker in [
    (host_cpp_path, "NCE_V17_SPLIT_FAIL"),
    (host_cpp_path, "NCE_V17_COALESCE_FAIL"),
    (lease_path, "NCE_V17_LEASE_RANGE"),
]:
    if marker not in p.read_text(encoding="utf-8"):
        raise SystemExit(f"V17 marker missing from {p}")

print("REALGAME_V17_PLACEHOLDER_LEASE_OVERLAP=PASS")
