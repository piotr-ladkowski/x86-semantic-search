; hello.asm - Linux x86-64, no C library: talks to the kernel with system calls
global _start

section .data
msg:    db "Hello, doc/x86!", 10        ; 10 = newline
msglen: equ $ - msg                      ; length of the string above

section .text
_start:
        mov     eax, 1                   ; system call number 1 = write
        mov     edi, 1                   ; 1st argument: file descriptor 1 = stdout
        lea     rsi, [rel msg]           ; 2nd argument: address of the bytes
        mov     edx, msglen              ; 3rd argument: how many bytes
        syscall                          ; kernel does the work; rcx and r11 are clobbered

        mov     eax, 60                  ; system call number 60 = exit
        xor     edi, edi                 ; 1st argument: exit status 0
        syscall

; tell the linker this program does not need an executable stack
section .note.GNU-stack noalloc noexec nowrite progbits
