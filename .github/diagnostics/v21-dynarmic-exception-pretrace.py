#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v21-dynarmic-exception-pretrace.py <arm_dynarmic_64.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

old = """        } else {\n            m_parent.LogBacktrace(m_process);\n            LOG_CRITICAL(Core_ARM, \"ExceptionRaised(exception = {}, pc = {:08X}, code = {:08X})\", static_cast<std::size_t>(exception), pc, m_memory.Read32(pc));\n        }\n"""

new = """        } else {\n            // V21: minimal clean-fault breadcrumb. Compare the backing-memory instruction with\n            // Dynarmic's effective code page. During Windows X18 fallback the latter contains the\n            // single-instruction override, so a difference identifies the fallback path without\n            // restoring the previous high-volume telemetry.\n            const u32 memory_code = m_memory.Read32(pc);\n            const u32 effective_code = MemoryReadCode(pc).value_or(0);\n            LOG_CRITICAL(Core_ARM,\n                         \"NCE_V21_DYNARMIC_EXCEPTION_PRETRACE exception={} pc={:#018x} memory_code={:#010x} effective_code={:#010x}\",\n                         static_cast<std::size_t>(exception), pc, memory_code, effective_code);\n            m_parent.LogBacktrace(m_process);\n            LOG_CRITICAL(Core_ARM, \"ExceptionRaised(exception = {}, pc = {:08X}, code = {:08X})\",\n                         static_cast<std::size_t>(exception), pc, memory_code);\n        }\n"""

count = text.count(old)
if count != 1:
    raise SystemExit(f"v21 target: expected exactly one source match, found {count}")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8", newline="\n")

marker = "NCE_V21_DYNARMIC_EXCEPTION_PRETRACE"
if marker not in text:
    raise SystemExit("V21 marker missing")

print("REALGAME_V21_DYNARMIC_EXCEPTION_PRETRACE=PASS")
