#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v25-teb-bounds-detail.py <arm_nce_windows.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


text = replace_once(
    text,
    "zero-sp",
    """    if (guest_sp == 0) {\n        return false;\n    }\n""",
    """    if (guest_sp == 0) {\n        LOG_ERROR(Core_ARM, \"NCE_V25_TEB_BOUNDS_FAIL stage=sp_zero\");\n        return false;\n    }\n""",
)

text = replace_once(
    text,
    "initial-virtual-query",
    """    MEMORY_BASIC_INFORMATION stack_mbi{};\n    if (VirtualQuery(reinterpret_cast<const void*>(guest_sp - 1), &stack_mbi,\n                     sizeof(stack_mbi)) == 0 ||\n        stack_mbi.AllocationBase == nullptr) {\n        return false;\n    }\n""",
    """    MEMORY_BASIC_INFORMATION stack_mbi{};\n    const SIZE_T stack_query_size =\n        VirtualQuery(reinterpret_cast<const void*>(guest_sp - 1), &stack_mbi, sizeof(stack_mbi));\n    if (stack_query_size == 0) {\n        LOG_ERROR(Core_ARM,\n                  \"NCE_V25_TEB_BOUNDS_FAIL stage=virtual_query sp={:#018x} query={:#018x} gle={}\",\n                  guest_sp, guest_sp - 1, static_cast<u32>(GetLastError()));\n        return false;\n    }\n    if (stack_mbi.AllocationBase == nullptr) {\n        LOG_ERROR(Core_ARM,\n                  \"NCE_V25_TEB_BOUNDS_FAIL stage=allocation_base_null sp={:#018x} mbi_base={:#018x} size={:#018x} state=0x{:08X} type=0x{:08X} protect=0x{:08X}\",\n                  guest_sp, reinterpret_cast<u64>(stack_mbi.BaseAddress),\n                  static_cast<u64>(stack_mbi.RegionSize), static_cast<u32>(stack_mbi.State),\n                  static_cast<u32>(stack_mbi.Type), static_cast<u32>(stack_mbi.Protect));\n        return false;\n    }\n""",
)

text = replace_once(
    text,
    "range-check",
    """    const auto guest_sp_value = static_cast<std::uintptr_t>(guest_sp);\n    if (guest_sp_value <= allocation_base || guest_sp_value >= allocation_end) {\n        return false;\n    }\n""",
    """    const auto guest_sp_value = static_cast<std::uintptr_t>(guest_sp);\n    if (guest_sp_value <= allocation_base || guest_sp_value >= allocation_end) {\n        LOG_ERROR(Core_ARM,\n                  \"NCE_V25_TEB_BOUNDS_FAIL stage=range sp={:#018x} allocation_base={:#018x} allocation_end={:#018x} sp_eq_end={} initial_base={:#018x} initial_size={:#018x} state=0x{:08X} type=0x{:08X} protect=0x{:08X}\",\n                  guest_sp, static_cast<u64>(allocation_base), static_cast<u64>(allocation_end),\n                  guest_sp_value == allocation_end, reinterpret_cast<u64>(stack_mbi.BaseAddress),\n                  static_cast<u64>(stack_mbi.RegionSize), static_cast<u32>(stack_mbi.State),\n                  static_cast<u32>(stack_mbi.Type), static_cast<u32>(stack_mbi.Protect));\n        return false;\n    }\n""",
)

path.write_text(text, encoding="utf-8", newline="\n")

updated = path.read_text(encoding="utf-8")
if "NCE_V25_TEB_BOUNDS_FAIL" not in updated or "sp_eq_end" not in updated:
    raise SystemExit("V25 marker missing")

print("REALGAME_V25_TEB_BOUNDS_DETAIL=PASS")
