#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v18-placeholder-topology.py <host_memory.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(label: str, old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    "split-topology-guard",
    """    void Split(size_t virtual_offset, size_t length) {\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(virtual_base + virtual_offset), length,\n                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {\n            LOG_CRITICAL(HW_Memory, \"Failed to split placeholder\");\n        }\n    }\n""",
    """    void Split(size_t virtual_offset, size_t length) {\n        auto* const address = virtual_base + virtual_offset;\n        MEMORY_BASIC_INFORMATION region{};\n        const SIZE_T queried = VirtualQuery(address, &region, sizeof(region));\n\n        // V18: a private HostMemory lease returns to an exact preserved placeholder before\n        // Restore() remaps the section-backed view. In that state there is nothing left to split.\n        // Calling MEM_PRESERVE_PLACEHOLDER again is invalid and returns ERROR_INVALID_ADDRESS.\n        if (queried != 0 && region.State == MEM_RESERVE && region.BaseAddress == address &&\n            static_cast<size_t>(region.RegionSize) == length) {\n            LOG_INFO(HW_Memory,\n                     \"NCE_V18_SPLIT_NOOP_EXACT_PLACEHOLDER addr={:#018x} length={:#x} type={:#x}\",\n                     reinterpret_cast<std::uintptr_t>(address), length,\n                     static_cast<unsigned long>(region.Type));\n            return;\n        }\n\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(address), length,\n                           MEM_RELEASE | MEM_PRESERVE_PLACEHOLDER)) {\n            const DWORD error = GetLastError();\n            LOG_CRITICAL(HW_Memory,\n                         \"NCE_V18_SPLIT_FAIL addr={:#018x} length={:#x} error={} query={} \"\n                         \"state={:#x} type={:#x} region_base={:#018x} region_size={:#x}\",\n                         reinterpret_cast<std::uintptr_t>(address), length, error, queried,\n                         queried != 0 ? static_cast<unsigned long>(region.State) : 0UL,\n                         queried != 0 ? static_cast<unsigned long>(region.Type) : 0UL,\n                         queried != 0 ? reinterpret_cast<std::uintptr_t>(region.BaseAddress) : 0ULL,\n                         queried != 0 ? static_cast<size_t>(region.RegionSize) : 0ULL);\n        }\n    }\n""",
)

replace_once(
    "coalesce-topology-guard",
    """    void Coalesce(size_t virtual_offset, size_t length) {\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(virtual_base + virtual_offset), length,\n                           MEM_RELEASE | MEM_COALESCE_PLACEHOLDERS)) {\n            LOG_CRITICAL(HW_Memory, \"Failed to coalesce placeholders\");\n        }\n    }\n""",
    """    void Coalesce(size_t virtual_offset, size_t length) {\n        auto* const address = virtual_base + virtual_offset;\n        const auto begin = reinterpret_cast<std::uintptr_t>(address);\n        const auto end = begin + length;\n        if (end < begin) {\n            LOG_CRITICAL(HW_Memory,\n                         \"NCE_V18_COALESCE_RANGE_OVERFLOW addr={:#018x} length={:#x}\", begin,\n                         length);\n            return;\n        }\n\n        // MEM_COALESCE_PLACEHOLDERS is valid only when the complete requested range consists of\n        // exact adjacent placeholders. Private NCE leases deliberately occupy holes in that\n        // topology, so defer coalescing while any part of the range is committed/non-placeholder.\n        auto cursor = begin;\n        size_t region_count = 0;\n        while (cursor < end) {\n            MEMORY_BASIC_INFORMATION region{};\n            const SIZE_T queried =\n                VirtualQuery(reinterpret_cast<const void*>(cursor), &region, sizeof(region));\n            if (queried == 0) {\n                LOG_CRITICAL(HW_Memory,\n                             \"NCE_V18_COALESCE_QUERY_FAIL addr={:#018x} length={:#x} cursor={:#018x} error={}\",\n                             begin, length, cursor, GetLastError());\n                return;\n            }\n\n            const auto region_begin = reinterpret_cast<std::uintptr_t>(region.BaseAddress);\n            const auto region_end = region_begin + static_cast<std::uintptr_t>(region.RegionSize);\n            if (region_end <= region_begin || region_begin != cursor || region_end > end ||\n                region.State != MEM_RESERVE) {\n                LOG_INFO(HW_Memory,\n                         \"NCE_V18_COALESCE_DEFER addr={:#018x} length={:#x} cursor={:#018x} \"\n                         \"state={:#x} type={:#x} region_base={:#018x} region_size={:#x}\",\n                         begin, length, cursor, static_cast<unsigned long>(region.State),\n                         static_cast<unsigned long>(region.Type), region_begin,\n                         static_cast<size_t>(region.RegionSize));\n                return;\n            }\n\n            cursor = region_end;\n            ++region_count;\n        }\n\n        if (region_count <= 1) {\n            LOG_INFO(HW_Memory,\n                     \"NCE_V18_COALESCE_NOOP_SINGLE_PLACEHOLDER addr={:#018x} length={:#x}\",\n                     begin, length);\n            return;\n        }\n\n        if (!VirtualFreeEx(process, reinterpret_cast<LPVOID>(address), length,\n                           MEM_RELEASE | MEM_COALESCE_PLACEHOLDERS)) {\n            LOG_CRITICAL(HW_Memory,\n                         \"NCE_V18_COALESCE_FAIL addr={:#018x} length={:#x} error={} regions={}\",\n                         begin, length, GetLastError(), region_count);\n        }\n    }\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")

for marker in [
    "NCE_V18_SPLIT_NOOP_EXACT_PLACEHOLDER",
    "NCE_V18_COALESCE_DEFER",
    "NCE_V18_COALESCE_NOOP_SINGLE_PLACEHOLDER",
]:
    if marker not in text:
        raise SystemExit(f"V18 marker missing: {marker}")

print("REALGAME_V18_PLACEHOLDER_TOPOLOGY=PASS")
