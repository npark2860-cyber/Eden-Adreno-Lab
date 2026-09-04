        AREA    |.text|, CODE, READONLY
        IMPORT  GetCurrentNceContextForGeneratedCode
        EXPORT  Imp007ExclusiveGetterProbe
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
