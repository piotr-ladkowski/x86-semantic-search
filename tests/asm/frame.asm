default rel
global frame_demo
section .text
frame_demo:                     ; long frame_demo(long x): keep x in a local variable and read it back
        push    rbp
        mov     rbp, rsp
        sub     rsp, 16         ; locals; rsp stays 16-aligned because push rbp realigned it
        mov     [rbp - 8], rdi
        mov     rax, [rbp - 8]
        leave                   ; mov rsp, rbp ; pop rbp
        ret
section .note.GNU-stack noalloc noexec nowrite progbits
