from pathlib import Path

path = Path('src/core/arm/nce/patcher.cpp')
text = path.read_text()

old = '#include "core/arm/nce/windows_x18_exclusive.h"\n'
new = old + '#include "core/arm/nce/windows_x18_lse.h"\n'
assert text.count(old) == 1
text = text.replace(old, new, 1)

anchor = '''        };\n#endif\n\n    // Loop through instructions, patching as needed.\n'''
assert text.count(anchor) == 1
lse_trampoline = r'''        };

    const auto WriteWindowsX18LseTrampoline =
        [&](ModuleDestLabel module_dest, const WindowsX18LsePlan& plan,
            oaknut::VectorCodeGenerator& cg) {
            constexpr u32 FullSaveFrameSize = 0x130;
            constexpr u32 VolatileVectorOffset = 0x90;
            constexpr u32 ScratchPairOffset = 0x110;
            constexpr u32 ContextScratchOffset = 0x120;
            constexpr u32 PairLinkRegisterOffset = 0x128;
            constexpr u32 ScalarLinkRegisterOffset = 0x120;
            constexpr u32 BlrBase = 0xD63F0000U;
            constexpr size_t GuestX18Offset =
                offsetof(GuestContext, cpu_registers) + sizeof(u64) * GuestX18Register;

            const oaknut::XReg value_reg{static_cast<int>(plan.value_scratch)};
            const oaknut::XReg context_reg{static_cast<int>(plan.context_scratch)};
            const bool has_pair_scratch = plan.pair_scratch_second != 0;
            const oaknut::XReg pair_reg{
                static_cast<int>(has_pair_scratch ? plan.pair_scratch_second : plan.value_scratch)};
            oaknut::Label getter_address;

            // Use the same conservative guest volatile save footprint as the proven classic
            // exclusive seam. LSE atomics are single instructions, so no reservation state crosses
            // this getter call; the native atomic instruction still owns the complete memory
            // transaction and its original A/R ordering bits.
            cg.SUB(SP, SP, FullSaveFrameSize);
            for (int i = 0; i <= 16; i += 2) {
                cg.STP(oaknut::XReg{i}, oaknut::XReg{i + 1}, SP, 8 * i);
            }
            for (int i = 0; i <= 6; i += 2) {
                cg.STP(oaknut::QReg{i}, oaknut::QReg{i + 1}, SP,
                       VolatileVectorOffset + 16 * i);
            }
            if (has_pair_scratch) {
                cg.STP(value_reg, pair_reg, SP, ScratchPairOffset);
                cg.STR(context_reg, SP, ContextScratchOffset);
                cg.STR(X30, SP, PairLinkRegisterOffset);
            } else {
                cg.STP(value_reg, context_reg, SP, ScratchPairOffset);
                cg.STR(X30, SP, ScalarLinkRegisterOffset);
            }

            cg.LDR(context_reg, getter_address);
            cg.dw(BlrBase | (plan.context_scratch << 5));
            cg.MOV(context_reg, X0);
            cg.LDR(context_reg, context_reg,
                   offsetof(NativeExecutionParameters, native_context));
            if (plan.reads_x18) {
                cg.LDR(value_reg, context_reg, GuestX18Offset);
            }
            if (plan.casp_pair_uses_x18) {
                cg.MOV(pair_reg, X19);
            }

            cg.LDR(X30, SP,
                   has_pair_scratch ? PairLinkRegisterOffset : ScalarLinkRegisterOffset);
            for (int i = 6; i >= 0; i -= 2) {
                cg.LDP(oaknut::QReg{i}, oaknut::QReg{i + 1}, SP,
                       VolatileVectorOffset + 16 * i);
            }
            for (int i = 16; i >= 0; i -= 2) {
                cg.LDP(oaknut::XReg{i}, oaknut::XReg{i + 1}, SP, 8 * i);
            }
            cg.ADD(SP, SP, FullSaveFrameSize);

            // Execute the real host LSE instruction. Only guest-x18 register fields were rewritten;
            // acquire/release bits and the complete atomic operation remain native and unchanged.
            cg.dw(plan.rewritten_instruction);

            if (plan.writes_x18) {
                cg.STR(value_reg, context_reg, GuestX18Offset);
            }
            if (plan.writes_x19) {
                cg.MOV(X19, pair_reg);
            }

            cg.SUB(SP, SP, FullSaveFrameSize);
            if (has_pair_scratch) {
                cg.LDP(value_reg, pair_reg, SP, ScratchPairOffset);
                cg.LDR(context_reg, SP, ContextScratchOffset);
            } else {
                cg.LDP(value_reg, context_reg, SP, ScratchPairOffset);
            }
            cg.ADD(SP, SP, FullSaveFrameSize);

            if (&cg == &c_pre) {
                this->BranchToModulePre(module_dest);
            } else {
                this->BranchToModule(module_dest);
            }

            cg.l(getter_address);
            cg.dx(static_cast<u64>(reinterpret_cast<uintptr_t>(
                &GetCurrentNceContextForGeneratedCode)));
        };
#endif

    // Loop through instructions, patching as needed.
'''
text = text.replace(anchor, lse_trampoline, 1)

old_scan = '''        if (auto exclusive = Exclusive{inst}; exclusive.Verify()) {\n'''
assert text.count(old_scan) == 1
new_scan = r'''#if defined(_WIN32)
        // Intercept the bounded single-instruction LSE families before Eden's broad Exclusive
        // signature. CASP overlaps Exclusive::Verify(); allowing it to fall through would set its
        // release bit via AsOrdered() and silently change guest ordering semantics.
        if (IsWindowsLseInstruction(inst)) {
            if (WindowsLseTouchesRegister(inst, GuestX18Register)) {
                const auto plan = BuildWindowsX18LsePlan(inst);
                if (!plan) {
                    // Never allow a recognized LSE touching guest x18 to execute with physical
                    // Windows x18 when a bounded non-conflicting rewrite cannot be constructed.
                    return false;
                }

                bool pre_buffer = false;
                const auto ret = AddRelocations(pre_buffer);
                if (pre_buffer) {
                    WriteWindowsX18LseTrampoline(ret, *plan, c_pre);
                } else {
                    WriteWindowsX18LseTrampoline(ret, *plan, c);
                }
            }
            // Non-x18 LSE instructions already execute correctly as native single instructions.
            // Continue here so CASP never reaches the legacy broad-exclusive AsOrdered pass.
            continue;
        }
#endif

        if (auto exclusive = Exclusive{inst}; exclusive.Verify()) {
'''
text = text.replace(old_scan, new_scan, 1)
path.write_text(text)
