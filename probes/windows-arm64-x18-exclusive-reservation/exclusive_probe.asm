        AREA    |.text|, CODE, READONLY
        IMPORT  GetCurrentNceContextForGeneratedCode
        EXPORT  Imp007ExclusiveGetterProbe
        EXPORT  Imp007ExclusiveFullSaveProbe
        EXPORT  Imp007ExclusiveAcquireReleaseProbe
        EXPORT  Imp007ExclusiveClrexProbe
        EXPORT  Imp007ExclusiveMismatchProbe

; uint32_t Imp007ExclusiveGetterProbe(uint64_t* target, void** observed)
;
; Establish the native reservation first, then execute the exact 32-byte generated-getter scratch
; pattern proven by IMP-005 before attempting STXR. x19 carries the loaded value across the C call;
; its original Windows ABI value is saved before the reservation is established.
Imp007ExclusiveGetterProbe PROC
        sub     sp, sp, #0x10
        str     x19, [sp, #0x00]

        ldxr    x19, [x0]

        sub     sp, sp, #0x20
        stp     x0, x1, [sp, #0x00]
        str     x30, [sp, #0x10]
        bl      GetCurrentNceContextForGeneratedCode
        ldr     x1, [sp, #0x08]
        str     x0, [x1]
        ldr     x30, [sp, #0x10]
        ldp     x0, x1, [sp, #0x00]
        add     sp, sp, #0x20

        add     x2, x19, #1
        stxr    w3, x2, [x0]
        mov     w0, w3

        ldr     x19, [sp, #0x00]
        add     sp, sp, #0x10
        ret
        ENDP

; uint32_t Imp007ExclusiveFullSaveProbe(uint64_t* target, void** observed)
;
; Model the conservative production STXR-side wrapper: after a reservation already exists, save all
; Windows volatile GPRs x0-x17, q0-q7, two nonvolatile helper scratches, and LR around the C-linkage
; CurrentNceContext getter. This is intentionally much heavier than the minimal IMP-005 getter
; wrapper. If STXR still succeeds, the production helper does not need to rely on compiler-specific
; getter clobber details to keep the guest reservation alive.
Imp007ExclusiveFullSaveProbe PROC
        sub     sp, sp, #0x20
        stp     x19, x20, [sp, #0x00]

        ldxr    x19, [x0]

        sub     sp, sp, #0x130
        stp     x0,  x1,  [sp, #0x00]
        stp     x2,  x3,  [sp, #0x10]
        stp     x4,  x5,  [sp, #0x20]
        stp     x6,  x7,  [sp, #0x30]
        stp     x8,  x9,  [sp, #0x40]
        stp     x10, x11, [sp, #0x50]
        stp     x12, x13, [sp, #0x60]
        stp     x14, x15, [sp, #0x70]
        stp     x16, x17, [sp, #0x80]
        stp     q0,  q1,  [sp, #0x90]
        stp     q2,  q3,  [sp, #0xB0]
        stp     q4,  q5,  [sp, #0xD0]
        stp     q6,  q7,  [sp, #0xF0]
        stp     x19, x20, [sp, #0x110]
        str     x30,      [sp, #0x120]

        bl      GetCurrentNceContextForGeneratedCode
        ldr     x1, [sp, #0x08]
        str     x0, [x1]

        ldr     x30,      [sp, #0x120]
        ldp     x19, x20, [sp, #0x110]
        ldp     q6,  q7,  [sp, #0xF0]
        ldp     q4,  q5,  [sp, #0xD0]
        ldp     q2,  q3,  [sp, #0xB0]
        ldp     q0,  q1,  [sp, #0x90]
        ldp     x16, x17, [sp, #0x80]
        ldp     x14, x15, [sp, #0x70]
        ldp     x12, x13, [sp, #0x60]
        ldp     x10, x11, [sp, #0x50]
        ldp     x8,  x9,  [sp, #0x40]
        ldp     x6,  x7,  [sp, #0x30]
        ldp     x4,  x5,  [sp, #0x20]
        ldp     x2,  x3,  [sp, #0x10]
        ldp     x0,  x1,  [sp, #0x00]
        add     sp, sp, #0x130

        add     x2, x19, #1
        stxr    w3, x2, [x0]
        mov     w0, w3

        ldp     x19, x20, [sp, #0x00]
        add     sp, sp, #0x20
        ret
        ENDP

; uint32_t Imp007ExclusiveAcquireReleaseProbe(uint64_t* target, void** observed)
; Same reservation-window traffic, using LDAXR/STLXR to cover acquire/release variants.
Imp007ExclusiveAcquireReleaseProbe PROC
        sub     sp, sp, #0x10
        str     x19, [sp, #0x00]

        ldaxr   x19, [x0]

        sub     sp, sp, #0x20
        stp     x0, x1, [sp, #0x00]
        str     x30, [sp, #0x10]
        bl      GetCurrentNceContextForGeneratedCode
        ldr     x1, [sp, #0x08]
        str     x0, [x1]
        ldr     x30, [sp, #0x10]
        ldp     x0, x1, [sp, #0x00]
        add     sp, sp, #0x20

        add     x2, x19, #1
        stlxr   w3, x2, [x0]
        mov     w0, w3

        ldr     x19, [sp, #0x00]
        add     sp, sp, #0x10
        ret
        ENDP

; uint32_t Imp007ExclusiveClrexProbe(uint64_t* target)
; A matching store-exclusive must fail after CLREX.
Imp007ExclusiveClrexProbe PROC
        ldxr    x1, [x0]
        add     x1, x1, #1
        clrex
        stxr    w2, x1, [x0]
        mov     w0, w2
        ret
        ENDP

; uint32_t Imp007ExclusiveMismatchProbe(uint64_t* reserved, uint64_t* other)
; A store-exclusive to a different address must not consume the reservation as a success.
Imp007ExclusiveMismatchProbe PROC
        ldxr    x2, [x0]
        add     x2, x2, #1
        stxr    w3, x2, [x1]
        mov     w0, w3
        ret
        ENDP

        END
