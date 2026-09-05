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
    """if (ARCHITECTURE_arm64 AND (ANDROID OR LINUX))\n    set(HAS_NCE 1)\n    add_compile_definitions(HAS_NCE=1)\nendif()\n""",
    """if (ARCHITECTURE_arm64 AND (ANDROID OR LINUX OR (WIN32 AND MSVC)))\n    set(HAS_NCE 1)\n    add_compile_definitions(HAS_NCE=1)\nendif()\n""",
)

replace_once(
    CORE,
    """if (HAS_NCE)\n    enable_language(C ASM)\n    set(CMAKE_ASM_FLAGS \"${CFLAGS} -x assembler-with-cpp\")\n\n    target_sources(core PRIVATE\n        arm/nce/arm_nce_asm_definitions.h\n        arm/nce/arm_nce.cpp\n        arm/nce/arm_nce.h\n        arm/nce/arm_nce.s\n        arm/nce/guest_context.h\n        arm/nce/instructions.h\n        arm/nce/interpreter_visitor.cpp\n        arm/nce/interpreter_visitor.h\n        arm/nce/patcher.cpp\n        arm/nce/patcher.h\n        arm/nce/visitor_base.h)\n    target_link_libraries(core PRIVATE merry::oaknut)\nendif()\n""",
    """if (HAS_NCE)\n    target_sources(core PRIVATE\n        arm/nce/arm_nce_asm_definitions.h\n        arm/nce/arm_nce.h\n        arm/nce/guest_context.h\n        arm/nce/instructions.h\n        arm/nce/patcher.cpp\n        arm/nce/patcher.h\n        arm/nce/visitor_base.h)\n\n    if (WIN32)\n        # Windows ARM64 keeps x18/TEB and host TPIDR platform-owned. Use the verified\n        # Windows transition/runtime owners and assemble the entry shim with MSVC armasm64.\n        get_filename_component(NCE_MSVC_ARM64_BIN \"${CMAKE_CXX_COMPILER}\" DIRECTORY)\n        set(NCE_ARMASM64 \"${NCE_MSVC_ARM64_BIN}/armasm64.exe\")\n        if (NOT EXISTS \"${NCE_ARMASM64}\")\n            message(FATAL_ERROR\n                \"Windows ARM64 NCE requires armasm64.exe next to the selected ARM64 compiler: ${NCE_ARMASM64}\")\n        endif()\n\n        set(NCE_WINDOWS_ENTRY_SOURCE\n            \"${CMAKE_CURRENT_SOURCE_DIR}/arm/nce/windows_nce_entry.asm\")\n        set(NCE_WINDOWS_ENTRY_OBJECT\n            \"${CMAKE_CURRENT_BINARY_DIR}/arm/nce/windows_nce_entry.obj\")\n        add_custom_command(\n            OUTPUT \"${NCE_WINDOWS_ENTRY_OBJECT}\"\n            COMMAND \"${NCE_ARMASM64}\" -nologo\n                    \"${NCE_WINDOWS_ENTRY_SOURCE}\" \"${NCE_WINDOWS_ENTRY_OBJECT}\"\n            DEPENDS \"${NCE_WINDOWS_ENTRY_SOURCE}\"\n            VERBATIM)\n        set_source_files_properties(\"${NCE_WINDOWS_ENTRY_OBJECT}\" PROPERTIES\n            GENERATED TRUE\n            EXTERNAL_OBJECT TRUE)\n\n        target_sources(core PRIVATE\n            arm/nce/arm_nce_windows.cpp\n            arm/nce/current_nce_context.h\n            arm/nce/windows_cross_thread_break.h\n            arm/nce/windows_exception_context.h\n            arm/nce/windows_generated_context.h\n            arm/nce/windows_nce_entry.asm\n            arm/nce/windows_nce_transition.cpp\n            arm/nce/windows_nce_transition.h\n            arm/nce/windows_x18_exclusive.h\n            arm/nce/windows_x18_fallback_runner.cpp\n            arm/nce/windows_x18_fallback_runner.h\n            arm/nce/windows_x18_fallback_trap.cpp\n            arm/nce/windows_x18_fallback_trap.h\n            arm/nce/windows_x18_lse.h\n            arm/nce/x18_classifier.cpp\n            arm/nce/x18_fallback.cpp\n            arm/nce/x18_fallback.h\n            arm/nce/x18_site_patcher.cpp\n            arm/nce/x18_site_patcher.h\n            \"${NCE_WINDOWS_ENTRY_OBJECT}\")\n        set_source_files_properties(arm/nce/windows_nce_entry.asm PROPERTIES HEADER_FILE_ONLY TRUE)\n    else()\n        enable_language(C ASM)\n        set(CMAKE_ASM_FLAGS \"${CFLAGS} -x assembler-with-cpp\")\n\n        target_sources(core PRIVATE\n            arm/nce/arm_nce.cpp\n            arm/nce/arm_nce.s\n            arm/nce/interpreter_visitor.cpp\n            arm/nce/interpreter_visitor.h)\n    endif()\n\n    target_link_libraries(core PRIVATE merry::oaknut)\nendif()\n""",
)

print("IMP008A_CMAKE_WIRING_PATCH=PASS")
