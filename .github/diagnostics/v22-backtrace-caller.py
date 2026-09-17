#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: v22-backtrace-caller.py <arm_interface.h> <arm_interface.cpp>")

header_path = Path(sys.argv[1])
cpp_path = Path(sys.argv[2])
header = header_path.read_text(encoding="utf-8")
cpp = cpp_path.read_text(encoding="utf-8")


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


header = replace_once(
    header,
    "source-location-include",
    "#include <span>\n#include <string>\n",
    "#include <span>\n#include <source_location>\n#include <string>\n",
)
header = replace_once(
    header,
    "backtrace-source-location-signature",
    "    void LogBacktrace(Kernel::KProcess* process) const;\n",
    "    void LogBacktrace(\n        Kernel::KProcess* process,\n        std::source_location caller = std::source_location::current()) const;\n",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

cpp = replace_once(
    cpp,
    "string-view-include",
    "#include \"common/logging.h\"\n",
    "#include <string_view>\n\n#include \"common/logging.h\"\n",
)
cpp = replace_once(
    cpp,
    "backtrace-caller-telemetry",
    "void ArmInterface::LogBacktrace(Kernel::KProcess* process) const {\n    Kernel::Svc::ThreadContext ctx;\n",
    "void ArmInterface::LogBacktrace(Kernel::KProcess* process, std::source_location caller) const {\n    const std::string_view caller_path{caller.file_name()};\n    const auto separator = caller_path.find_last_of(\"/\\\\\");\n    const auto caller_file =\n        caller_path.substr(separator == std::string_view::npos ? 0 : separator + 1);\n    LOG_ERROR(Core_ARM, \"NCE_V22_BACKTRACE_CALLER file={} line={} function={}\", caller_file,\n              caller.line(), caller.function_name());\n\n    Kernel::Svc::ThreadContext ctx;\n",
)
cpp_path.write_text(cpp, encoding="utf-8", newline="\n")

for path, marker in [
    (header_path, "std::source_location caller"),
    (cpp_path, "NCE_V22_BACKTRACE_CALLER"),
]:
    if marker not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"V22 marker missing from {path}")

print("REALGAME_V22_BACKTRACE_CALLER=PASS")
