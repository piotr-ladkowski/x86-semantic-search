; win64.asm - Microsoft x64 calling convention (Windows), plus a call into the C runtime
default rel
extern printf
global add3, sum5, keep_rsi, say_answer

section .rdata
fmt:    db "answer = %d", 10, 0

section .text
add3:                           ; long long add3(long long a, long long b, long long c): rcx, rdx, r8
        lea     rax, [rcx + rdx]
        add     rax, r8
        ret

sum5:                           ; five arguments: the first four are in registers
        lea     rax, [rcx + rdx]    ; arg1 + arg2
        add     rax, r8             ; arg3
        add     rax, r9             ; arg4
        add     rax, [rsp + 40]     ; arg5: above the return address (8) and the 32-byte shadow space
        ret

keep_rsi:                       ; rsi and rdi are callee-saved on Windows (not on Linux)
        push    rsi
        mov     rsi, rcx
        mov     rax, rsi
        pop     rsi
        ret

say_answer:                     ; void say_answer(void): printf("answer = %d\n", 42)
        sub     rsp, 40         ; 32-byte shadow space + 8 to realign (rsp is 8 mod 16 on entry)
        lea     rcx, [fmt]      ; 1st argument: rcx
        mov     edx, 42         ; 2nd argument: rdx
        call    printf
        add     rsp, 40
        ret
