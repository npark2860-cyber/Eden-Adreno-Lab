#!/usr/bin/env python3
from pathlib import Path

ROOT = Path("CMakeLists.txt")
CORE = Path("src/core/CMakeLists.txt")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    ROOT,
    "if (ARCHITECTURE_arm64 AND (ANDROID OR LINUX OR (WIN32 AND MSVC)))",
    "if (ARCHITECTURE_arm64 AND (ANDROID OR LINUX OR WIN32))",
)

replace_once(
    CORE,
    """        get_filename_component(NCE_MSVC_ARM64_BIN \"${CMAKE_CXX_COMPILER}\" DIRECTORY)\n        set(NCE_ARMASM64 \"${NCE_MSVC_ARM64_BIN}/armasm64.exe\")\n        if (NOT EXISTS \"${NCE_ARMASM64}\")\n            message(FATAL_ERROR\n                \"Windows ARM64 NCE requires armasm64.exe next to the selected ARM64 compiler: ${NCE_ARMASM64}\")\n        endif()\n\n        set(NCE_WINDOWS_ENTRY_SOURCE\n            \"${CMAKE_CURRENT_SOURCE_DIR}/arm/nce/windows_nce_entry.asm\")\n        set(NCE_WINDOWS_ENTRY_OBJECT\n            \"${CMAKE_CURRENT_BINARY_DIR}/arm/nce/windows_nce_entry.obj\")\n""",
    """        get_filename_component(NCE_WINDOWS_COMPILER_BIN \"${CMAKE_CXX_COMPILER}\" DIRECTORY)\n        set(NCE_ARMASM64 \"${NCE_WINDOWS_COMPILER_BIN}/armasm64.exe\")\n        if (NOT EXISTS \"${NCE_ARMASM64}\")\n            # Eden's normal Windows ARM64 build uses MSYS2 CLANGARM64, while the verified\n            # Windows entry shim is assembled by the Visual Studio ARM64 assembler already\n            # present on supported Windows build hosts. Do not add a second assembler.\n            file(GLOB NCE_ARMASM64_CANDIDATES\n                \"C:/Program Files/Microsoft Visual Studio/2022/*/VC/Tools/MSVC/*/bin/Hostarm64/arm64/armasm64.exe\")\n            if (NCE_ARMASM64_CANDIDATES)\n                list(SORT NCE_ARMASM64_CANDIDATES COMPARE NATURAL ORDER DESCENDING)\n                list(GET NCE_ARMASM64_CANDIDATES 0 NCE_ARMASM64)\n            endif()\n        endif()\n        if (NOT EXISTS \"${NCE_ARMASM64}\")\n            message(FATAL_ERROR\n                \"Windows ARM64 NCE requires the Visual Studio ARM64 armasm64.exe tool\")\n        endif()\n\n        set(NCE_WINDOWS_ENTRY_SOURCE\n            \"${CMAKE_CURRENT_SOURCE_DIR}/arm/nce/windows_nce_entry.asm\")\n        set(NCE_WINDOWS_ENTRY_OBJECT\n            \"${CMAKE_CURRENT_BINARY_DIR}/windows_nce_entry.obj\")\n""",
)

print("IMP008A_CMAKE_NORMAL_WINDOWS_ARM64_WIRING_PATCH=PASS")
