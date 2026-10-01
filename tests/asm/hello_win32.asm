; hello_win32.asm - Windows x64, no C runtime: only Win32 API calls from kernel32.dll
default rel
extern GetStdHandle
extern WriteFile
extern ExitProcess
global start

section .data
msg:    db "Hello, Win32", 13, 10
msglen: equ $ - msg

section .bss
written: resd 1                          ; WriteFile reports how many bytes it wrote here

section .text
start:
        sub     rsp, 40                  ; 32 bytes shadow space + 8 for the 5th argument; keeps rsp 16-aligned
        mov     ecx, -11                 ; STD_OUTPUT_HANDLE
        call    GetStdHandle             ; handle returned in rax

        mov     rcx, rax                 ; 1st: hFile
        lea     rdx, [msg]               ; 2nd: lpBuffer
        mov     r8d, msglen              ; 3rd: nNumberOfBytesToWrite
        lea     r9, [written]            ; 4th: lpNumberOfBytesWritten
        mov     qword [rsp + 32], 0      ; 5th: lpOverlapped (NULL) goes on the stack, just above the shadow space
        call    WriteFile

        xor     ecx, ecx                 ; exit code 0
        call    ExitProcess
