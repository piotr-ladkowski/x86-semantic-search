; hello_win.asm - Windows x64, uses the C runtime (the CRT start-up code calls main)
default rel
extern puts
global main

section .rdata
msg:    db "Hello from Windows", 0

section .text
main:
        sub     rsp, 40                  ; 32 bytes shadow space + 8 to realign (rsp is 8 mod 16 on entry)
        lea     rcx, [msg]               ; 1st argument (Microsoft x64): rcx
        call    puts
        xor     eax, eax                 ; return 0
        add     rsp, 40
        ret
