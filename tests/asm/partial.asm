default rel
global partial_demo
section .text
partial_demo:                   ; void partial_demo(unsigned long out[3])
        mov  rax, -1          ; rax = 0xFFFFFFFFFFFFFFFF
        mov  eax, 1           ; rax = 0x0000000000000001  (upper 32 bits cleared)
        mov  [rdi], rax

        mov  rax, -1
        mov  ax, 1            ; rax = 0xFFFFFFFFFFFF0001  (upper 48 bits kept)
        mov  [rdi + 8], rax

        mov  rax, -1
        mov  eax, eax         ; rax = 0x00000000FFFFFFFF  (zero-extend the low half)
        mov  [rdi + 16], rax
        ret
section .note.GNU-stack noalloc noexec nowrite progbits
