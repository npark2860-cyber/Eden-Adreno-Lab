; SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
; SPDX-License-Identifier: GPL-3.0-or-later

        AREA    |.text|, CODE, READONLY
        EXPORT  WindowsNceEnterGuest
        EXPORT  WindowsNceEntryBreakpoint

; Keep these constants in lock-step with arm_nce_asm_definitions.h.
GuestContextHostContext EQU 0x320
HostContextRegs         EQU 0x0
HostContextVregs        EQU 0x60
HostContextSp           EQU 0xE0

; uint64_t WindowsNceEnterGuest(GuestContext* guest)
;
; Save the Windows ARM64 ABI nonvolatile state while still on the host stack, then enter a fixed
; breakpoint gate. The VEH owner replaces the breakpoint CONTEXT with guest architectural state.
; Physical x18 and TPIDR_EL0 are never written here.
WindowsNceEnterGuest PROC
        add     x9, x0, #GuestContextHostContext

        stp     x19, x20, [x9, #(HostContextRegs + 0x00)]
        stp     x21, x22, [x9, #(HostContextRegs + 0x10)]
        stp     x23, x24, [x9, #(HostContextRegs + 0x20)]
        stp     x25, x26, [x9, #(HostContextRegs + 0x30)]
        stp     x27, x28, [x9, #(HostContextRegs + 0x40)]
        stp     x29, x30, [x9, #(HostContextRegs + 0x50)]

        stp     q8,  q9,  [x9, #(HostContextVregs + 0x00)]
        stp     q10, q11, [x9, #(HostContextVregs + 0x20)]
        stp     q12, q13, [x9, #(HostContextVregs + 0x40)]
        stp     q14, q15, [x9, #(HostContextVregs + 0x60)]

        mov     x10, sp
        str     x10, [x9, #HostContextSp]

WindowsNceEntryBreakpoint
        brk     #0xF000

        ; A matching VEH must never resume at the following instruction.
        brk     #0xF000
        ENDP

        END
