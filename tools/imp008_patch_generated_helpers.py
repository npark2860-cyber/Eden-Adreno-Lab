from pathlib import Path
import re

path = Path("src/core/arm/nce/patcher.cpp")
text = path.read_text(encoding="utf-8")

include_old = '''#if defined(_WIN32)\n#include "core/arm/nce/windows_nce_transition.h"\n#include "core/arm/nce/windows_x18_exclusive.h"'''
include_new = '''#if defined(_WIN32)\n#include "core/arm/nce/windows_generated_context.h"\n#include "core/arm/nce/windows_nce_transition.h"\n#include "core/arm/nce/windows_x18_exclusive.h"'''
if text.count(include_old) != 1:
    raise RuntimeError("expected one Windows include anchor")
text = text.replace(include_old, include_new, 1)


def replace_between(start_marker: str, end_marker: str, replacement: str) -> None:
    global text
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"missing start marker: {start_marker}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"missing end marker: {end_marker}")
    text = text[:start] + replacement.rstrip() + "\n\n" + text[end:]


replace_between(
    "void Patcher::WriteLoadContext(oaknut::VectorCodeGenerator& cg) {",
    "void Patcher::WriteSaveContext(oaknut::VectorCodeGenerator& cg) {",
    r'''void Patcher::WriteLoadContext(oaknut::VectorCodeGenerator& cg) {
    // This function was called, which modifies X30, so use that as a scratch register.
    // SP contains the guest X30, so save our return X30 to SP + 8, since we have allocated 16 bytes
    // of stack.
    cg.STR(X30, SP, 8);
#if defined(_WIN32)
    WriteWindowsCurrentNceParametersLookup(cg, X30);
#else
    cg.MRS(X30, oaknut::SystemReg::TPIDR_EL0);
#endif
    cg.LDR(X30, X30, offsetof(NativeExecutionParameters, native_context));

    // Load system registers.
    cg.LDR(W0, X30, offsetof(GuestContext, fpsr));
    cg.MSR(oaknut::SystemReg::FPSR, X0);
    cg.LDR(W0, X30, offsetof(GuestContext, fpcr));
    cg.MSR(oaknut::SystemReg::FPCR, X0);
    cg.LDR(W0, X30, offsetof(GuestContext, nzcv));
    cg.MSR(oaknut::SystemReg::NZCV, X0);

    // Load all vector registers.
    static constexpr size_t VEC_OFF = offsetof(GuestContext, vector_registers);
    for (int i = 0; i <= 30; i += 2) {
        cg.LDP(oaknut::QReg{i}, oaknut::QReg{i + 1}, X30, VEC_OFF + 16 * i);
    }

#if defined(_WIN32)
    // Restore guest GPRs without assigning architectural x18 to the Windows TEB register.
    for (int i = 0; i <= 16; i += 2) {
        cg.LDP(oaknut::XReg{i}, oaknut::XReg{i + 1}, X30, 8 * i);
    }
    for (int i = 19; i <= 27; i += 2) {
        cg.LDP(oaknut::XReg{i}, oaknut::XReg{i + 1}, X30, 8 * i);
    }
    cg.LDR(X29, X30, 8 * 29);
#else
    // Load all general-purpose registers except X30.
    for (int i = 0; i <= 28; i += 2) {
        cg.LDP(oaknut::XReg{i}, oaknut::XReg{i + 1}, X30, 8 * i);
    }
#endif

    // Reload our return X30 from the stack and return.
    // The patch code will reload the guest X30 for us.
    cg.LDR(X30, SP, 8);
    cg.RET();
}''')

replace_between(
    "void Patcher::WriteSaveContext(oaknut::VectorCodeGenerator& cg) {",
    "void Patcher::WriteSvcTrampoline(",
    r'''void Patcher::WriteSaveContext(oaknut::VectorCodeGenerator& cg) {
    // This function was called, which modifies X30, so use that as a scratch register.
    // SP contains the guest X30, so save our X30 to SP + 8, since we have allocated 16 bytes of
    // stack.
    cg.STR(X30, SP, 8);
#if defined(_WIN32)
    WriteWindowsCurrentNceParametersLookup(cg, X30);
#else
    cg.MRS(X30, oaknut::SystemReg::TPIDR_EL0);
#endif
    cg.LDR(X30, X30, offsetof(NativeExecutionParameters, native_context));

#if defined(_WIN32)
    // Save guest GPRs without copying the physical Windows x18/TEB value into virtual guest x18.
    for (int i = 0; i <= 16; i += 2) {
        cg.STP(oaknut::XReg{i}, oaknut::XReg{i + 1}, X30, 8 * i);
    }
    for (int i = 19; i <= 27; i += 2) {
        cg.STP(oaknut::XReg{i}, oaknut::XReg{i + 1}, X30, 8 * i);
    }
    cg.STR(X29, X30, 8 * 29);
#else
    // Store all general-purpose registers except X30.
    for (int i = 0; i <= 28; i += 2) {
        cg.STP(oaknut::XReg{i}, oaknut::XReg{i + 1}, X30, 8 * i);
    }
#endif

    // Store all vector registers.
    static constexpr size_t VEC_OFF = offsetof(GuestContext, vector_registers);
    for (int i = 0; i <= 30; i += 2) {
        cg.STP(oaknut::QReg{i}, oaknut::QReg{i + 1}, X30, VEC_OFF + 16 * i);
    }

    // Store guest system registers, X30 and SP, using X0 as a scratch register.
    cg.STR(X0, SP, PRE_INDEXED, -16);
    cg.LDR(X0, SP, 16);
    cg.STR(X0, X30, 8 * 30);
    cg.ADD(X0, SP, 32);
    cg.STR(X0, X30, offsetof(GuestContext, sp));
    cg.MRS(X0, oaknut::SystemReg::FPSR);
    cg.STR(W0, X30, offsetof(GuestContext, fpsr));
    cg.MRS(X0, oaknut::SystemReg::FPCR);
    cg.STR(W0, X30, offsetof(GuestContext, fpcr));
    cg.MRS(X0, oaknut::SystemReg::NZCV);
    cg.STR(W0, X30, offsetof(GuestContext, nzcv));
    cg.LDR(X0, SP, POST_INDEXED, 16);

    // Reload our return X30 from the stack, and return.
    cg.LDR(X30, SP, 8);
    cg.RET();
}''')

replace_between(
    "void Patcher::WriteMrsHandler(",
    "void Patcher::WriteMsrHandler(",
    r'''void Patcher::WriteMrsHandler(ModuleDestLabel module_dest, oaknut::XReg dest_reg,
                              oaknut::SystemReg src_reg, oaknut::VectorCodeGenerator& cg) {
#if defined(_WIN32)
    if (dest_reg.index() == GuestX18Register) {
        // Architectural x18 is virtual state on Windows. Never write the TEB platform register.
        cg.STP(X0, X1, SP, PRE_INDEXED, -16);
        WriteWindowsCurrentNceParametersLookup(cg, X0);
        if (src_reg == oaknut::SystemReg::TPIDRRO_EL0) {
            cg.LDR(X1, X0, offsetof(NativeExecutionParameters, tpidrro_el0));
        } else {
            cg.LDR(X1, X0, offsetof(NativeExecutionParameters, tpidr_el0));
        }
        cg.LDR(X0, X0, offsetof(NativeExecutionParameters, native_context));
        cg.STR(X1, X0, offsetof(GuestContext, cpu_registers) + sizeof(u64) * GuestX18Register);
        cg.LDP(X0, X1, SP, POST_INDEXED, 16);
    } else if (dest_reg.index() != 31) {
        WriteWindowsCurrentNceParametersLookup(cg, dest_reg);
        if (src_reg == oaknut::SystemReg::TPIDRRO_EL0) {
            cg.LDR(dest_reg, dest_reg, offsetof(NativeExecutionParameters, tpidrro_el0));
        } else {
            cg.LDR(dest_reg, dest_reg, offsetof(NativeExecutionParameters, tpidr_el0));
        }
    }
#else
    // Retrieve emulated TLS register from GuestContext.
    cg.MRS(dest_reg, oaknut::SystemReg::TPIDR_EL0);
    if (src_reg == oaknut::SystemReg::TPIDRRO_EL0) {
        cg.LDR(dest_reg, dest_reg, offsetof(NativeExecutionParameters, tpidrro_el0));
    } else {
        cg.LDR(dest_reg, dest_reg, offsetof(NativeExecutionParameters, tpidr_el0));
    }
#endif

    // Jump back to the instruction after the emulated MRS.
    if (&cg == &c_pre)
        this->BranchToModulePre(module_dest);
    else
        this->BranchToModule(module_dest);
}''')

replace_between(
    "void Patcher::WriteMsrHandler(",
    "void Patcher::WriteCntfrqHandler(",
    r'''void Patcher::WriteMsrHandler(ModuleDestLabel module_dest, oaknut::XReg src_reg, oaknut::VectorCodeGenerator& cg) {
    const auto scratch_reg = src_reg.index() == 0 ? X1 : X0;
    cg.STR(scratch_reg, SP, PRE_INDEXED, -16);

#if defined(_WIN32)
    WriteWindowsCurrentNceParametersLookup(cg, scratch_reg);
    if (src_reg.index() == GuestX18Register) {
        // Source x18 is the virtual guest value, never the live physical Windows TEB register.
        const auto value_reg = scratch_reg.index() == 0 ? X1 : X0;
        cg.STR(value_reg, SP, PRE_INDEXED, -16);
        cg.LDR(value_reg, scratch_reg, offsetof(NativeExecutionParameters, native_context));
        cg.LDR(value_reg, value_reg,
               offsetof(GuestContext, cpu_registers) + sizeof(u64) * GuestX18Register);
        cg.STR(value_reg, scratch_reg, offsetof(NativeExecutionParameters, tpidr_el0));
        cg.LDR(value_reg, SP, POST_INDEXED, 16);
    } else {
        cg.STR(src_reg, scratch_reg, offsetof(NativeExecutionParameters, tpidr_el0));
    }
#else
    // Save guest value to NativeExecutionParameters::tpidr_el0.
    cg.MRS(scratch_reg, oaknut::SystemReg::TPIDR_EL0);
    cg.STR(src_reg, scratch_reg, offsetof(NativeExecutionParameters, tpidr_el0));
#endif

    // Restore scratch register.
    cg.LDR(scratch_reg, SP, POST_INDEXED, 16);

    // Jump back to the instruction after the emulated MSR.
    if (&cg == &c_pre)
        this->BranchToModulePre(module_dest);
    else
        this->BranchToModule(module_dest);
}''')

replace_between(
    "void Patcher::LockContext(oaknut::VectorCodeGenerator& cg) {",
    "void Patcher::UnlockContext(oaknut::VectorCodeGenerator& cg) {",
    r'''void Patcher::LockContext(oaknut::VectorCodeGenerator& cg) {
    oaknut::Label retry;

    // Save scratches.
    cg.STP(X0, X1, SP, PRE_INDEXED, -16);

    // Reload lock pointer.
    cg.l(retry);
    cg.CLREX();
#if defined(_WIN32)
    WriteWindowsCurrentNceParametersLookup(cg, X0);
#else
    cg.MRS(X0, oaknut::SystemReg::TPIDR_EL0);
#endif
    cg.ADD(X0, X0, offsetof(NativeExecutionParameters, lock));

    static_assert(SpinLockLocked == 0);

    // Load-linked with acquire ordering.
    cg.LDAXR(W1, X0);

    // If the value was SpinLockLocked, clear monitor and retry.
    cg.CBZ(W1, retry);

    // Store-conditional SpinLockLocked with relaxed ordering.
    cg.STXR(W1, WZR, X0);

    // If we failed to store, retry.
    cg.CBNZ(W1, retry);

    // We succeeded! Reload scratches.
    cg.LDP(X0, X1, SP, POST_INDEXED, 16);
}''')

# UnlockContext is the final function in the file.
start = text.find("void Patcher::UnlockContext(oaknut::VectorCodeGenerator& cg) {")
end = text.find("\n} // namespace Core::NCE", start)
if start < 0 or end < 0:
    raise RuntimeError("unable to locate UnlockContext")
replacement = r'''void Patcher::UnlockContext(oaknut::VectorCodeGenerator& cg) {
    // Save scratches.
    cg.STP(X0, X1, SP, PRE_INDEXED, -16);

    // Load lock pointer.
#if defined(_WIN32)
    WriteWindowsCurrentNceParametersLookup(cg, X0);
#else
    cg.MRS(X0, oaknut::SystemReg::TPIDR_EL0);
#endif
    cg.ADD(X0, X0, offsetof(NativeExecutionParameters, lock));

    // Load SpinLockUnlocked.
    cg.MOV(W1, SpinLockUnlocked);

    // Store value with release ordering.
    cg.STLR(W1, X0);

    // Load scratches.
    cg.LDP(X0, X1, SP, POST_INDEXED, 16);
}'''
text = text[:start] + replacement + text[end:]

path.write_text(text, encoding="utf-8")
print("IMP008_GENERATED_HELPER_PATCH=APPLIED")
