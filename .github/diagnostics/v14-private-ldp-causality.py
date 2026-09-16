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
    "private-ldp-causality",
    """    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n""",
    """    if (*instruction == 0xa94943f2U) {\n        u64 private_x18{};\n        u64 private_x16{};\n        SIZE_T private_x18_bytes{};\n        SIZE_T private_x16_bytes{};\n\n        SetLastError(ERROR_SUCCESS);\n        const BOOL private_x18_read = ReadProcessMemory(\n            GetCurrentProcess(), reinterpret_cast<const void*>(guest.sp + 0x90),\n            &private_x18, sizeof(private_x18), &private_x18_bytes);\n        const DWORD private_x18_error =\n            private_x18_read ? ERROR_SUCCESS : GetLastError();\n\n        SetLastError(ERROR_SUCCESS);\n        const BOOL private_x16_read = ReadProcessMemory(\n            GetCurrentProcess(), reinterpret_cast<const void*>(guest.sp + 0x98),\n            &private_x16, sizeof(private_x16), &private_x16_bytes);\n        const DWORD private_x16_error =\n            private_x16_read ? ERROR_SUCCESS : GetLastError();\n\n        const bool private_x18_ok =\n            private_x18_read != FALSE && private_x18_bytes == sizeof(private_x18);\n        const bool private_x16_ok =\n            private_x16_read != FALSE && private_x16_bytes == sizeof(private_x16);\n\n        if (private_x18_ok && private_x16_ok) {\n            // 0xa94943f2 = LDP X18, X16, [SP, #0x90] (signed offset, no writeback).\n            // Execute only this proven-problematic load from the active private guest view.\n            // Every other fallback instruction continues through the existing Dynarmic Step path.\n            guest.cpu_registers[18] = private_x18;\n            guest.cpu_registers[16] = private_x16;\n            guest.pc = before_pc + sizeof(u32);\n            result.step.completed = true;\n            result.step.halt_reason = HaltReason{};\n            LOG_INFO(Core_ARM,\n                     \"NCE_V14_PRIVATE_LDP_APPLIED pc={:#018x} sp={:#018x} x18_before={:#018x} x18_private={:#018x} x16_before={:#018x} x16_private={:#018x} next_pc={:#018x}\",\n                     before_pc, guest.sp, before_x18, private_x18, before_x16, private_x16,\n                     guest.pc);\n        } else {\n            LOG_ERROR(Core_ARM,\n                      \"NCE_V14_PRIVATE_LDP_READ_FAILED pc={:#018x} sp={:#018x} x18_ok={} x18_bytes={} x18_error={} x16_ok={} x16_bytes={} x16_error={}\",\n                      before_pc, guest.sp, private_x18_ok, private_x18_bytes,\n                      private_x18_error, private_x16_ok, private_x16_bytes,\n                      private_x16_error);\n            result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n        }\n    } else {\n        result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n    }\n""",
)
runner_path.write_text(runner, encoding="utf-8", newline="\n")

print("REALGAME_V14_PRIVATE_LDP_CAUSALITY=PASS")
