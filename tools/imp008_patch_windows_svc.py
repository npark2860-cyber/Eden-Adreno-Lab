from pathlib import Path

path = Path("src/core/arm/nce/patcher.cpp")
text = path.read_text(encoding="utf-8")

start_marker = "void Patcher::WriteSvcTrampoline("
end_marker = "void Patcher::WriteMrsHandler("
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("unable to locate WriteSvcTrampoline")

replacement = r'''void Patcher::WriteSvcTrampoline(ModuleDestLabel module_dest, u32 svc_id,
                                 oaknut::VectorCodeGenerator& cg, oaknut::Label& save_ctx,
                                 oaknut::Label& load_ctx) {
    // Determine if we're writing to the pre-patch buffer.
    const bool is_pre = (&cg == &c_pre);
#if defined(_WIN32)
    // Windows re-entry uses WindowsNceEnterGuest instead of the Linux load-context trampoline.
    (void)load_ctx;
#endif

    // We are about to start saving state, so we need to lock the context.
    this->LockContext(cg);

    // Store guest X30 to the stack. Then, save the context and restore the stack.
    // This will save all registers except PC, but we know PC at patch time.
    cg.STR(X30, SP, PRE_INDEXED, -16);
    cg.BL(save_ctx);
    cg.LDR(X30, SP, POST_INDEXED, 16);

    // Now that we've saved all guest registers, ordinary scratch registers are available.
    oaknut::Label pc_after_svc;
#if defined(_WIN32)
    WriteWindowsCurrentNceParametersLookup(cg, X1);
#else
    cg.MRS(X1, oaknut::SystemReg::TPIDR_EL0);
#endif
    cg.LDR(X1, X1, offsetof(NativeExecutionParameters, native_context));
    cg.LDR(X2, pc_after_svc);
    cg.STR(X2, X1, offsetof(GuestContext, pc));

    // Store SVC number to execute when we return.
    cg.MOV(X2, svc_id);
    cg.STR(W2, X1, offsetof(GuestContext, svc));

    // We are calling a SVC. Clear esr_el1 and return it.
    static_assert(std::is_same_v<std::underlying_type_t<HaltReason>, u64>);
    oaknut::Label retry;
    cg.ADD(X2, X1, offsetof(GuestContext, esr_el1));
    cg.l(retry);
    cg.LDAXR(X0, X2);
    cg.STLXR(W3, XZR, X2);
    cg.CBNZ(W3, retry);

    // Add the calling-SVC flag. X0 is the host return value.
    cg.ORR(X0, X0, static_cast<u64>(HaltReason::SupervisorCall));

    // Offset the GuestContext pointer to the HostContext member.
    // STP/LDP have limited ranges, so all offsets below are from HostContext.
    cg.ADD(X1, X1, offsetof(GuestContext, host_ctx));

#if defined(_WIN32)
    // WindowsNceEnterGuest saved the host ABI continuation without repurposing physical TPIDR_EL0.
    // Restore only the saved host SP/nonvolatile state and return to its C++ caller. Physical x18
    // and physical TPIDR_EL0 stay platform-owned throughout.
    cg.LDR(X2, X1, offsetof(HostContext, host_sp));
    cg.MOV(SP, X2);
#else
    // Reload host TPIDR_EL0 and SP on the Linux/Android path.
    static_assert(offsetof(HostContext, host_sp) + 8 == offsetof(HostContext, host_tpidr_el0));
    cg.LDP(X2, X3, X1, offsetof(HostContext, host_sp));
    cg.MOV(SP, X2);
    cg.MSR(oaknut::SystemReg::TPIDR_EL0, X3);
#endif

    // Load callee-saved host registers and return to host.
    static constexpr size_t HOST_REGS_OFF = offsetof(HostContext, host_saved_regs);
    static constexpr size_t HOST_VREGS_OFF = offsetof(HostContext, host_saved_vregs);
    cg.LDP(X19, X20, X1, HOST_REGS_OFF);
    cg.LDP(X21, X22, X1, HOST_REGS_OFF + 2 * sizeof(u64));
    cg.LDP(X23, X24, X1, HOST_REGS_OFF + 4 * sizeof(u64));
    cg.LDP(X25, X26, X1, HOST_REGS_OFF + 6 * sizeof(u64));
    cg.LDP(X27, X28, X1, HOST_REGS_OFF + 8 * sizeof(u64));
    cg.LDP(X29, X30, X1, HOST_REGS_OFF + 10 * sizeof(u64));
    cg.LDP(Q8, Q9, X1, HOST_VREGS_OFF);
    cg.LDP(Q10, Q11, X1, HOST_VREGS_OFF + 2 * sizeof(u128));
    cg.LDP(Q12, Q13, X1, HOST_VREGS_OFF + 4 * sizeof(u128));
    cg.LDP(Q14, Q15, X1, HOST_VREGS_OFF + 6 * sizeof(u128));
    cg.RET();

    // This address is the post-SVC entry point selected by RunThread when GuestContext::pc equals
    // the instruction after the emulated SVC.
    if (is_pre) {
        curr_patch->m_trampolines_pre.push_back({cg.offset(), module_dest});
    } else {
        curr_patch->m_trampolines.push_back({cg.offset(), module_dest});
    }

#if defined(_WIN32)
    // WindowsNceEnterGuest has already restored guest x0-x15, x19-x30, SIMD/status and guest SP.
    // It intentionally carries GuestContext in x17 and the selected trampoline in x16. Unlock the
    // scheduler-owned NCE context, restore the two guest scratch registers, then use a direct branch
    // so no architectural guest register is consumed as a PC carrier.
    this->UnlockContext(cg);
    cg.LDR(X16, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 16);
    cg.LDR(X17, X17, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 17);

    if (is_pre)
        this->BranchToModulePre(module_dest);
    else
        this->BranchToModule(module_dest);
#else
    // Linux/Android host called this location. Save the return address so the existing assembly
    // entry path can unwind the stack properly when jumping back.
    cg.MRS(X2, oaknut::SystemReg::TPIDR_EL0);
    cg.LDR(X2, X2, offsetof(NativeExecutionParameters, native_context));
    cg.ADD(X0, X2, offsetof(GuestContext, host_ctx));
    cg.STR(X30, X0, offsetof(HostContext, host_saved_regs) + 11 * sizeof(u64));

    // Reload all guest registers except X30 and PC.
    // The function also expects 16 bytes of stack already allocated.
    cg.STR(X30, SP, PRE_INDEXED, -16);
    cg.BL(load_ctx);
    cg.LDR(X30, SP, POST_INDEXED, 16);

    // Use X1 as a scratch register to restore X30.
    cg.STR(X1, SP, PRE_INDEXED, -16);
    cg.MRS(X1, oaknut::SystemReg::TPIDR_EL0);
    cg.LDR(X1, X1, offsetof(NativeExecutionParameters, native_context));
    cg.LDR(X30, X1, offsetof(GuestContext, cpu_registers) + sizeof(u64) * 30);
    cg.LDR(X1, SP, POST_INDEXED, 16);

    // Unlock the context.
    this->UnlockContext(cg);

    // Jump back to the instruction after the emulated SVC.
    if (is_pre)
        this->BranchToModulePre(module_dest);
    else
        this->BranchToModule(module_dest);
#endif

    // Store PC after call.
    cg.l(pc_after_svc);
    if (is_pre)
        this->WriteModulePcPre(module_dest);
    else
        this->WriteModulePc(module_dest);
}'''

text = text[:start] + replacement + "\n\n" + text[end:]
path.write_text(text, encoding="utf-8")
print("IMP008_WINDOWS_SVC_PATCH=APPLIED")
