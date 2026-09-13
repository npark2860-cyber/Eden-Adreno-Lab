from pathlib import Path
import textwrap


def replay(path: str, section: str | None = None) -> None:
    text = Path(path).read_text(encoding="utf-8")
    if section is not None:
        text = text[text.index(section):]
    start_marker = "          @'\n"
    end_marker = "\n          '@ | python -"
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    script = textwrap.dedent(text[start:end])
    exec(compile(script, f"<{path}>", "exec"), {})


replay(".github/workflows/build-windows-arm64-nce-teb-bidirectional-return-validation.yml")
replay(
    ".github/workflows/build-windows-arm64-nce-unknown-exception-diagnostic.yml",
    "      - name: Inject unknown guest exception observer",
)
replay(
    ".github/workflows/build-windows-arm64-nce-reentry-breadcrumb-diagnostic.yml",
    "      - name: Inject host-stack exception observer and reentry breadcrumbs",
)

path = Path("src/core/arm/nce/arm_nce_windows.cpp")
text = path.read_text(encoding="utf-8")
old = """        if (breadcrumb_index == 30 && breadcrumb_post && m_guest_ctx.svc == 0x27U &&\n            m_guest_ctx.sp != 0) {\n            static u64 cinc_saved_lr{};\n            cinc_saved_lr = 0xFFFFFFFFFFFFFFFFULL;\n            const bool cinc_saved_lr_read = process->GetMemory().ReadBlock(\n                Common::ProcessAddress{m_guest_ctx.sp + 8}, &cinc_saved_lr, sizeof(cinc_saved_lr));\n            LOG_ERROR(Core_ARM,\n                      \"IMP008_CINC_STACK_LR n={} sp={:016X} read={} saved_lr={:016X} x30={:016X}\",\n                      breadcrumb_index, m_guest_ctx.sp, cinc_saved_lr_read, cinc_saved_lr,\n                      m_guest_ctx.cpu_registers[30]);\n        }\n"""
new = """        if (breadcrumb_index == 30 && breadcrumb_post && m_guest_ctx.svc == 0x27U &&\n            m_guest_ctx.sp != 0) {\n            const u64 cinc_witness_sp = m_guest_ctx.sp;\n            std::array<u64, 2> cinc_witness_frame{};\n            const bool cinc_witness_read = process->GetMemory().ReadBlock(\n                Common::ProcessAddress{cinc_witness_sp}, cinc_witness_frame.data(),\n                sizeof(cinc_witness_frame));\n            const u64 cinc_saved_x19 = cinc_witness_frame[0];\n            const u64 cinc_saved_lr = cinc_witness_frame[1];\n            LOG_ERROR(Core_ARM,\n                      \"IMP008_CINC_WITNESS_EPILOGUE_BYPASS n={} sp={:016X} read={} saved_x19={:016X} saved_lr={:016X} old_x30={:016X}\",\n                      breadcrumb_index, cinc_witness_sp, cinc_witness_read, cinc_saved_x19,\n                      cinc_saved_lr, m_guest_ctx.cpu_registers[30]);\n            if (cinc_witness_read) {\n                m_guest_ctx.cpu_registers[19] = cinc_saved_x19;\n                m_guest_ctx.cpu_registers[30] = cinc_saved_lr;\n                m_guest_ctx.sp = cinc_witness_sp + 0x10;\n                LOG_ERROR(Core_ARM,\n                          \"IMP008_CINC_WITNESS_EPILOGUE_APPLIED n={} new_sp={:016X} new_x19={:016X} new_x30={:016X}\",\n                          breadcrumb_index, m_guest_ctx.sp, m_guest_ctx.cpu_registers[19],\n                          m_guest_ctx.cpu_registers[30]);\n\n                const u64 cinc_checkpoint_sp = m_guest_ctx.sp;\n                std::array<u64, 2> cinc_checkpoint_frame{};\n                const bool cinc_checkpoint_read = process->GetMemory().ReadBlock(\n                    Common::ProcessAddress{cinc_checkpoint_sp}, cinc_checkpoint_frame.data(),\n                    sizeof(cinc_checkpoint_frame));\n                const u64 cinc_saved_x29 = cinc_checkpoint_frame[0];\n                const u64 cinc_caller_lr = cinc_checkpoint_frame[1];\n                LOG_ERROR(Core_ARM,\n                          \"IMP008_CINC_CHECKPOINT_EPILOGUE_BYPASS n={} sp={:016X} read={} saved_x29={:016X} caller_lr={:016X} old_x30={:016X}\",\n                          breadcrumb_index, cinc_checkpoint_sp, cinc_checkpoint_read,\n                          cinc_saved_x29, cinc_caller_lr, m_guest_ctx.cpu_registers[30]);\n                if (cinc_checkpoint_read) {\n                    m_guest_ctx.cpu_registers[29] = cinc_saved_x29;\n                    m_guest_ctx.cpu_registers[30] = cinc_caller_lr;\n                    m_guest_ctx.sp = cinc_checkpoint_sp + 0x190;\n                    LOG_ERROR(Core_ARM,\n                              \"IMP008_CINC_CHECKPOINT_EPILOGUE_APPLIED n={} new_sp={:016X} new_x29={:016X} new_x30={:016X}\",\n                              breadcrumb_index, m_guest_ctx.sp, m_guest_ctx.cpu_registers[29],\n                              m_guest_ctx.cpu_registers[30]);\n\n                    const u64 cinc_raw_arg = m_guest_ctx.sp + 0x38;\n                    const u64 cinc_raw_bl = cinc_caller_lr + 4;\n                    LOG_ERROR(Core_ARM,\n                              \"IMP008_CINC_CALLER_ARG_SETUP_BYPASS n={} caller_pc={:016X} bl_pc={:016X} raw_arg={:016X} old_x0={:016X} old_x30={:016X}\",\n                              breadcrumb_index, cinc_caller_lr, cinc_raw_bl, cinc_raw_arg,\n                              m_guest_ctx.cpu_registers[0], m_guest_ctx.cpu_registers[30]);\n                    m_guest_ctx.cpu_registers[0] = cinc_raw_arg;\n                    m_guest_ctx.cpu_registers[30] = cinc_raw_bl;\n                    LOG_ERROR(Core_ARM,\n                              \"IMP008_CINC_CALLER_ARG_SETUP_APPLIED n={} new_x0={:016X} new_x30={:016X}\",\n                              breadcrumb_index, m_guest_ctx.cpu_registers[0],\n                              m_guest_ctx.cpu_registers[30]);\n                }\n            }\n        }\n"""

count = text.count(old)
if count != 1:
    raise SystemExit(f"checkpoint epilogue anchor count={count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("NCE_CINC_CHECKPOINT_EPILOGUE_BYPASS_INJECTION=PASS")
print("NCE_CINC_CALLER_ARG_SETUP_BYPASS_INJECTION=PASS")
