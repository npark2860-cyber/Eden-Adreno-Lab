; SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
; SPDX-License-Identifier: GPL-3.0-or-later

        AREA    |.text|, CODE, READONLY
        EXPORT  ProbeEnterGuestContext
        EXTERN  ProbeRestoreGuestContext

GuestContextHostContext EQU 0x320
HostContextRegs         EQU 0x000
HostContextVregs        EQU 0x060
HostContextSp           EQU 0x0E0

; uint64_t ProbeEnterGuestContext(GuestContext* guest)
;
; Save the host continuation in the exact layout consumed by the production Windows SVC
; trampoline, then hand the guest to ProbeRestoreGuestContext. That helper uses the Windows
; CONTEXT restore API to enter GuestContext::pc with all guest registers restored except physical
; x18, which remains Windows/TEB-owned.
ProbeEnterGuestContext PROC
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

        bl      ProbeRestoreGuestContext

        ; RtlRestoreContext must not return through this path.
        brk     #1000
        ENDP

        END
