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
    "preproducer-code-sweep",
    """                for (int delta = -0x100; delta <= 0x40; delta += 4) {\n                    const u64 code_pc = before_pc + delta;\n                    if (memory.IsValidVirtualAddressRange(code_pc, sizeof(u32))) {\n                        LOG_INFO(Core_ARM,\n                                 \"NCE_V11_CODE pc={:#018x} delta={} instr={:#010x}\",\n                                 code_pc, delta, memory.Read32(code_pc));\n                    }\n                }\n""",
    """                const u64 code_start =\n                    state.first_pc >= 0x400 ? state.first_pc - 0x400 : state.first_pc;\n                const u64 code_end = before_pc + 0x40;\n                LOG_INFO(Core_ARM,\n                         \"NCE_V12_CODE_RANGE start={:#018x} first_pc={:#018x} ldp_pc={:#018x} end={:#018x}\",\n                         code_start, state.first_pc, before_pc, code_end);\n                for (u64 code_pc = code_start; code_pc <= code_end; code_pc += 4) {\n                    if (memory.IsValidVirtualAddressRange(code_pc, sizeof(u32))) {\n                        LOG_INFO(Core_ARM, \"NCE_V12_CODE pc={:#018x} instr={:#010x}\",\n                                 code_pc, memory.Read32(code_pc));\n                    }\n                }\n""",
)
runner_path.write_text(runner, encoding="utf-8", newline="\n")

print("REALGAME_V12_PREPRODUCER_CODE_SWEEP=PASS")
