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
    "unordered-map-include",
    """#include \"core/arm/nce/windows_x18_fallback_runner.h\"\n\n#include \"common/logging.h\"\n""",
    """#include \"core/arm/nce/windows_x18_fallback_runner.h\"\n\n#include <unordered_map>\n\n#include \"common/logging.h\"\n""",
)
runner = replace_once(
    runner,
    "stack-history-probe",
    """    const u64 before_pc = guest.pc;\n    const u64 before_x16 = guest.cpu_registers[16];\n    const u64 before_x18 = guest.cpu_registers[18];\n    if (*instruction == 0xa94943f2U && thread != nullptr && thread->GetOwnerProcess() != nullptr) {\n        auto& memory = thread->GetOwnerProcess()->GetMemory();\n        const u64 stack_x18 = memory.Read64(guest.sp + 0x90);\n        const u64 stack_x16 = memory.Read64(guest.sp + 0x98);\n        LOG_INFO(Core_ARM,\n                 \"NCE_V10_LDP_STACK_BEFORE pc={:#018x} sp={:#018x} stack90_x18={:#018x} stack98_x16={:#018x} x16_before={:#018x} x18_before={:#018x}\",\n                 before_pc, guest.sp, stack_x18, stack_x16, before_x16, before_x18);\n    }\n""",
    """    const u64 before_pc = guest.pc;\n    const u64 before_x16 = guest.cpu_registers[16];\n    const u64 before_x18 = guest.cpu_registers[18];\n    if (thread != nullptr && thread->GetOwnerProcess() != nullptr) {\n        auto& memory = thread->GetOwnerProcess()->GetMemory();\n        if (memory.IsValidVirtualAddressRange(guest.sp + 0x90, 0x10)) {\n            const u64 stack_x18 = memory.Read64(guest.sp + 0x90);\n            const u64 stack_x16 = memory.Read64(guest.sp + 0x98);\n            struct StackTrackState {\n                u64 stack_x18{};\n                u64 stack_x16{};\n                u64 first_pc{};\n                u64 observations{};\n                bool initialized{};\n            };\n            static thread_local std::unordered_map<u64, StackTrackState> stack_track;\n            auto& state = stack_track[guest.sp];\n            if (!state.initialized) {\n                state.initialized = true;\n                state.stack_x18 = stack_x18;\n                state.stack_x16 = stack_x16;\n                state.first_pc = before_pc;\n                LOG_INFO(Core_ARM,\n                         \"NCE_V11_STACK_TRACK_INIT sp={:#018x} pc={:#018x} instr={:#010x} stack90_x18={:#018x} stack98_x16={:#018x}\",\n                         guest.sp, before_pc, *instruction, stack_x18, stack_x16);\n            } else if (state.stack_x18 != stack_x18 || state.stack_x16 != stack_x16) {\n                LOG_INFO(Core_ARM,\n                         \"NCE_V11_STACK_TRACK_CHANGE sp={:#018x} pc={:#018x} instr={:#010x} prev90_x18={:#018x} stack90_x18={:#018x} prev98_x16={:#018x} stack98_x16={:#018x}\",\n                         guest.sp, before_pc, *instruction, state.stack_x18, stack_x18,\n                         state.stack_x16, stack_x16);\n                state.stack_x18 = stack_x18;\n                state.stack_x16 = stack_x16;\n            }\n            ++state.observations;\n            if (*instruction == 0xa94943f2U) {\n                LOG_INFO(Core_ARM,\n                         \"NCE_V11_STACK_TRACK_LDP sp={:#018x} pc={:#018x} first_pc={:#018x} observations={} stack90_x18={:#018x} stack98_x16={:#018x}\",\n                         guest.sp, before_pc, state.first_pc, state.observations, stack_x18,\n                         stack_x16);\n                LOG_INFO(Core_ARM,\n                         \"NCE_V10_LDP_STACK_BEFORE pc={:#018x} sp={:#018x} stack90_x18={:#018x} stack98_x16={:#018x} x16_before={:#018x} x18_before={:#018x}\",\n                         before_pc, guest.sp, stack_x18, stack_x16, before_x16, before_x18);\n                for (int delta = -0x100; delta <= 0x40; delta += 4) {\n                    const u64 code_pc = before_pc + delta;\n                    if (memory.IsValidVirtualAddressRange(code_pc, sizeof(u32))) {\n                        LOG_INFO(Core_ARM,\n                                 \"NCE_V11_CODE pc={:#018x} delta={} instr={:#010x}\",\n                                 code_pc, delta, memory.Read32(code_pc));\n                    }\n                }\n            }\n        }\n    }\n""",
)
runner_path.write_text(runner, encoding="utf-8", newline="\n")

print("REALGAME_V11_STACK_HISTORY=PASS")
