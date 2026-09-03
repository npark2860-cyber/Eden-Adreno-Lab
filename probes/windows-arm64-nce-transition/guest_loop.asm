        AREA    |.text|, CODE, READONLY
        EXPORT  Imp005GuestLoop

Imp005GuestLoop PROC
        mov     w1, #1
        str     w1, [x0]
spin
        b       spin
        ENDP

        END
