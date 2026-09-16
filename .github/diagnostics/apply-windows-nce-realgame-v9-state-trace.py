from pathlib import Path
import sys

arm_path = Path(sys.argv[1])
runner_path = Path(sys.argv[2])


def replace_once(text: str, label: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, found {count}")
    return text.replace(old, new, 1)


arm = arm_path.read_text(encoding="utf-8")
arm = replace_once(
    arm,
    "pending-fault-invalidate-trace",
    """            if (process->GetMemory().InvalidateNCE(Common::ProcessAddress{pending_fault_page},\n                                                   Memory::YUZU_PAGESIZE)) {\n                continue;\n            }\n\n            if (m_guest_ctx.pc != pending_fault_address) {\n                m_guest_ctx.pc += sizeof(u32);\n                continue;\n            }\n\n            hr = HaltReason::PrefetchAbort;\n            break;\n""",
    """            const bool invalidated = process->GetMemory().InvalidateNCE(\n                Common::ProcessAddress{pending_fault_page}, Memory::YUZU_PAGESIZE);\n            LOG_INFO(Core_ARM,\n                     \"NCE_V9_FAULT pc={:#018x} addr={:#018x} page={:#018x} invalidated={} prefetch={}\",\n                     m_guest_ctx.pc, pending_fault_address, pending_fault_page, invalidated,\n                     m_guest_ctx.pc == pending_fault_address);\n            if (invalidated) {\n                continue;\n            }\n\n            if (m_guest_ctx.pc != pending_fault_address) {\n                LOG_INFO(Core_ARM, \"NCE_V9_FAULT_ACTION skip pc={:#018x} next={:#018x}\",\n                         m_guest_ctx.pc, m_guest_ctx.pc + sizeof(u32));\n                m_guest_ctx.pc += sizeof(u32);\n                continue;\n            }\n\n            LOG_INFO(Core_ARM, \"NCE_V9_FAULT_ACTION prefetch_abort pc={:#018x}\", m_guest_ctx.pc);\n            hr = HaltReason::PrefetchAbort;\n            break;\n""",
)
arm_path.write_text(arm, encoding="utf-8", newline="\n")

runner = runner_path.read_text(encoding="utf-8")
runner = replace_once(
    runner,
    "logging-include",
    """#include \"core/arm/nce/windows_x18_fallback_runner.h\"\n\n#include \"core/arm/dynarmic/arm_dynarmic_64.h\"\n""",
    """#include \"core/arm/nce/windows_x18_fallback_runner.h\"\n\n#include \"common/logging.h\"\n#include \"core/arm/dynarmic/arm_dynarmic_64.h\"\n""",
)
runner = replace_once(
    runner,
    "x18-step-trace",
    """    result.metadata_found = true;\n    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n    return result;\n""",
    """    result.metadata_found = true;\n    const u64 before_pc = guest.pc;\n    const u64 before_x18 = guest.cpu_registers[18];\n    LOG_INFO(Core_ARM, \"NCE_V9_X18_BEFORE pc={:#018x} instr={:#010x} x18={:#018x} sp={:#018x}\",\n             before_pc, *instruction, before_x18, guest.sp);\n    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n    LOG_INFO(Core_ARM,\n             \"NCE_V9_X18_AFTER before_pc={:#018x} pc={:#018x} instr={:#010x} x18_before={:#018x} x18={:#018x} completed={} halt={:#018x}\",\n             before_pc, guest.pc, *instruction, before_x18, guest.cpu_registers[18],\n             result.step.completed, static_cast<u64>(result.step.halt_reason));\n    return result;\n""",
)
runner_path.write_text(runner, encoding="utf-8", newline="\n")

print("REALGAME_V9_STATE_TRACE=PASS")
