from pathlib import Path
import sys

runner_path = Path(sys.argv[1])


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


runner = runner_path.read_text(encoding="utf-8")
runner = replace_once(
    runner,
    "windows-header",
    """#include \"core/arm/nce/windows_x18_fallback_runner.h\"\n\n#include <unordered_map>\n""",
    """#include \"core/arm/nce/windows_x18_fallback_runner.h\"\n\n#define WIN32_LEAN_AND_MEAN\n#include <windows.h>\n\n#include <unordered_map>\n""",
)
runner = replace_once(
    runner,
    "dual-view-probe",
    """                LOG_INFO(Core_ARM,\n                         \"NCE_V10_LDP_STACK_BEFORE pc={:#018x} sp={:#018x} stack90_x18={:#018x} stack98_x16={:#018x} x16_before={:#018x} x18_before={:#018x}\",\n                         before_pc, guest.sp, stack_x18, stack_x16, before_x16, before_x18);\n                const u64 code_start =\n""",
    """                LOG_INFO(Core_ARM,\n                         \"NCE_V10_LDP_STACK_BEFORE pc={:#018x} sp={:#018x} stack90_x18={:#018x} stack98_x16={:#018x} x16_before={:#018x} x18_before={:#018x}\",\n                         before_pc, guest.sp, stack_x18, stack_x16, before_x16, before_x18);\n\n                u64 direct90{};\n                u64 direct98{};\n                SIZE_T direct90_bytes{};\n                SIZE_T direct98_bytes{};\n                SetLastError(ERROR_SUCCESS);\n                const BOOL direct90_read = ReadProcessMemory(\n                    GetCurrentProcess(), reinterpret_cast<const void*>(guest.sp + 0x90),\n                    &direct90, sizeof(direct90), &direct90_bytes);\n                const DWORD direct90_error = direct90_read ? ERROR_SUCCESS : GetLastError();\n                SetLastError(ERROR_SUCCESS);\n                const BOOL direct98_read = ReadProcessMemory(\n                    GetCurrentProcess(), reinterpret_cast<const void*>(guest.sp + 0x98),\n                    &direct98, sizeof(direct98), &direct98_bytes);\n                const DWORD direct98_error = direct98_read ? ERROR_SUCCESS : GetLastError();\n                const bool direct90_ok = direct90_read != FALSE && direct90_bytes == sizeof(direct90);\n                const bool direct98_ok = direct98_read != FALSE && direct98_bytes == sizeof(direct98);\n\n                LOG_INFO(Core_ARM,\n                         \"NCE_V13_DUAL_VIEW pc={:#018x} sp={:#018x} direct90_ok={} direct90={:#018x} direct90_bytes={} direct90_error={} backing90={:#018x} direct98_ok={} direct98={:#018x} direct98_bytes={} direct98_error={} backing98={:#018x}\",\n                         before_pc, guest.sp, direct90_ok, direct90, direct90_bytes,\n                         direct90_error, stack_x18, direct98_ok, direct98, direct98_bytes,\n                         direct98_error, stack_x16);\n                const u64 code_start =\n""",
)
runner_path.write_text(runner, encoding="utf-8", newline="\n")

print("REALGAME_V13_DUAL_VIEW=PASS")
