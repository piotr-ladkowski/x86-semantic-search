; hello_libc.asm - Linux x86-64, uses the C library (the C runtime starts main)
default rel                              ; address data relative to rip by default
extern puts
global main

section .rodata
msg:    db "Hello from libc", 0          ; C strings end with a zero byte

section .text
main:
        push    rbp                      ; on entry rsp is 8 mod 16; this push makes it 16-aligned
        lea     rdi, [msg]               ; 1st argument (System V): rdi
        call    puts wrt ..plt           ; call through the PLT so it also links as a PIE
        xor     eax, eax                 ; return value 0 -> exit status 0
        pop     rbp
        ret

; tell the linker this program does not need an executable stack
section .note.GNU-stack noalloc noexec nowrite progbits
