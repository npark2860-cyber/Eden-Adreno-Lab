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
    "fault-site-state-probe",
    """            LOG_INFO(Core_ARM,\n                     \"NCE_V9_FAULT pc={:#018x} addr={:#018x} page={:#018x} invalidated={} prefetch={}\",\n                     m_guest_ctx.pc, pending_fault_address, pending_fault_page, invalidated,\n                     m_guest_ctx.pc == pending_fault_address);\n""",
    """            const u32 fault_instruction = process->GetMemory().Read32(m_guest_ctx.pc);\n            LOG_INFO(Core_ARM,\n                     \"NCE_V10_FAULT_STATE pc={:#018x} instr={:#010x} addr={:#018x} x16={:#018x} x18={:#018x} sp={:#018x}\",\n                     m_guest_ctx.pc, fault_instruction, pending_fault_address,\n                     m_guest_ctx.cpu_registers[16], m_guest_ctx.cpu_registers[18], m_guest_ctx.sp);\n            LOG_INFO(Core_ARM,\n                     \"NCE_V9_FAULT pc={:#018x} addr={:#018x} page={:#018x} invalidated={} prefetch={}\",\n                     m_guest_ctx.pc, pending_fault_address, pending_fault_page, invalidated,\n                     m_guest_ctx.pc == pending_fault_address);\n""",
)
arm_path.write_text(arm, encoding="utf-8", newline="\n")

runner = runner_path.read_text(encoding="utf-8")
runner = replace_once(
    runner,
    "ldp-stack-source-probe",
    """    result.metadata_found = true;\n    const u64 before_pc = guest.pc;\n    const u64 before_x18 = guest.cpu_registers[18];\n    LOG_INFO(Core_ARM, \"NCE_V9_X18_BEFORE pc={:#018x} instr={:#010x} x18={:#018x} sp={:#018x}\",\n             before_pc, *instruction, before_x18, guest.sp);\n    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n    LOG_INFO(Core_ARM,\n             \"NCE_V9_X18_AFTER before_pc={:#018x} pc={:#018x} instr={:#010x} x18_before={:#018x} x18={:#018x} completed={} halt={:#018x}\",\n             before_pc, guest.pc, *instruction, before_x18, guest.cpu_registers[18],\n             result.step.completed, static_cast<u64>(result.step.halt_reason));\n    return result;\n""",
    """    result.metadata_found = true;\n    const u64 before_pc = guest.pc;\n    const u64 before_x16 = guest.cpu_registers[16];\n    const u64 before_x18 = guest.cpu_registers[18];\n    if (*instruction == 0xa94943f2U && thread != nullptr && thread->GetOwnerProcess() != nullptr) {\n        auto& memory = thread->GetOwnerProcess()->GetMemory();\n        const u64 stack_x18 = memory.Read64(guest.sp + 0x90);\n        const u64 stack_x16 = memory.Read64(guest.sp + 0x98);\n        LOG_INFO(Core_ARM,\n                 \"NCE_V10_LDP_STACK_BEFORE pc={:#018x} sp={:#018x} stack90_x18={:#018x} stack98_x16={:#018x} x16_before={:#018x} x18_before={:#018x}\",\n                 before_pc, guest.sp, stack_x18, stack_x16, before_x16, before_x18);\n    }\n    LOG_INFO(Core_ARM, \"NCE_V9_X18_BEFORE pc={:#018x} instr={:#010x} x18={:#018x} sp={:#018x}\",\n             before_pc, *instruction, before_x18, guest.sp);\n    result.step = X18Fallback::Step(*m_backend, thread, guest, *instruction);\n    LOG_INFO(Core_ARM,\n             \"NCE_V9_X18_AFTER before_pc={:#018x} pc={:#018x} instr={:#010x} x18_before={:#018x} x18={:#018x} completed={} halt={:#018x}\",\n             before_pc, guest.pc, *instruction, before_x18, guest.cpu_registers[18],\n             result.step.completed, static_cast<u64>(result.step.halt_reason));\n    if (*instruction == 0xa94943f2U) {\n        LOG_INFO(Core_ARM,\n                 \"NCE_V10_LDP_STACK_AFTER before_pc={:#018x} pc={:#018x} x16_before={:#018x} x16={:#018x} x18_before={:#018x} x18={:#018x}\",\n                 before_pc, guest.pc, before_x16, guest.cpu_registers[16], before_x18,\n                 guest.cpu_registers[18]);\n    }\n    return result;\n""",
)
runner_path.write_text(runner, encoding="utf-8", newline="\n")

print("REALGAME_V10_LDP_STACK_PROBE=PASS")
