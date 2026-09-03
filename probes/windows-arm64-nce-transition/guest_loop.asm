        AREA    |.text|, CODE, READONLY
        IMPORT  GetCurrentNceContextForGeneratedCode
        EXPORT  Imp005EntryTrampoline
        EXPORT  Imp005GuestLoop

; x17 carries GuestContext from WindowsNceEnterGuest. Restore the two scratch GPRs and then use a
; direct branch so no guest register is consumed as the final PC carrier.
Imp005EntryTrampoline PROC
        ldr     x16, [x17, #0x080]
        ldr     x17, [x17, #0x088]
        b       Imp005GuestLoop
        ENDP

; x0 = entered flag, x2 = output slot for observed CurrentNceContext pointer.
; Use exactly 32 bytes of balanced guest-stack scratch around the fixed C-linkage getter call.
Imp005GuestLoop PROC
        sub     sp, sp, #0x20
        stp     x0, x2, [sp, #0x00]
        str     x30, [sp, #0x10]
        bl      GetCurrentNceContextForGeneratedCode
        ldr     x2, [sp, #0x08]
        str     x0, [x2]
        ldr     x30, [sp, #0x10]
        ldp     x0, x2, [sp, #0x00]
        add     sp, sp, #0x20

        mov     w1, #1
        str     w1, [x0]
spin
        b       spin
        ENDP

        END
