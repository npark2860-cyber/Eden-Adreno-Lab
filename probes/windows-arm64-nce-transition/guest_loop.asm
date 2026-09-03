        AREA    |.text|, CODE, READONLY
        EXPORT  Imp005EntryTrampoline
        EXPORT  Imp005GuestLoop

; x17 carries GuestContext from WindowsNceEnterGuest. Restore the two scratch GPRs and then use a
; direct branch so no guest register is consumed as the final PC carrier.
Imp005EntryTrampoline PROC
        ldr     x16, [x17, #0x080]
        ldr     x17, [x17, #0x088]
        b       Imp005GuestLoop
        ENDP

Imp005GuestLoop PROC
        mov     w1, #1
        str     w1, [x0]
spin
        b       spin
        ENDP

        END
