; sysv.asm - System V AMD64 calling convention (Linux), plus a call into the C library
default rel
extern printf
global add3, sum7, keep_rbx, say_answer

section .rodata
fmt:    db "answer = %d", 10, 0

section .text
add3:                           ; long add3(long a, long b, long c): a=rdi, b=rsi, c=rdx
        lea     rax, [rdi + rsi]
        add     rax, rdx
        ret                     ; the result goes back in rax

sum7:                           ; seven integer arguments: the first six are in registers
        lea     rax, [rdi + rsi]    ; arg1 + arg2
        add     rax, rdx            ; arg3
        add     rax, rcx            ; arg4
        add     rax, r8             ; arg5
        add     rax, r9             ; arg6
        add     rax, [rsp + 8]      ; arg7 is on the stack, just above the return address
        ret

keep_rbx:                       ; long keep_rbx(long x): uses rbx, so it must save and restore it
        push    rbx
        mov     rbx, rdi
        mov     rax, rbx
        pop     rbx
        ret

say_answer:                     ; void say_answer(void): printf("answer = %d\n", 42)
        push    rbp             ; entry rsp is 8 mod 16; this push makes it 16-aligned for the call
        lea     rdi, [fmt]      ; 1st argument: the format string
        mov     esi, 42         ; 2nd argument: the value for %d
        xor     eax, eax        ; al = number of vector registers used: none (printf is variadic)
        call    printf wrt ..plt
        pop     rbp
        ret

section .note.GNU-stack noalloc noexec nowrite progbits
