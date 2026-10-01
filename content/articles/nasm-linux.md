---
slug: nasm-linux
title: "Assemble, link and run a NASM program on Linux"
summary: Install NASM, assemble, link with ld or gcc, run and read the exit status. Two tested programs (with and without the C library), the linker warning everyone hits, and the usual mistakes.
tags: [nasm, linux, toolchain, tutorial]
status: draft
related_instructions: [syscall, mov, lea, call, ret, xor, push, pop]
sdm_refs:
  - "Vol. 2, SYSCALL—Fast System Call (RCX receives the return address, R11 receives RFLAGS)"
extra_sources:
  - "Everything below was run on Debian 12 with NASM 2.16.01, GNU ld 2.40 and GCC 12.2 (x86-64): both programs print their text and exit with status 0; the .note.GNU-stack warning appeared without the fix line and disappeared with it; a missing 'global _start' produced the quoted ld warning; 'ret' from _start segfaulted (exit status 139)."
  - "System V AMD64 ABI draft 0.99.6, Appendix A.2 (Linux system call registers: rax = number, rdi, rsi, rdx, r10, r8, r9 = arguments)."
  - "Wikibooks, 'x86 Assembly/Print Version', sections 'Netwide Assembler (NASM)', 'NASM Syntax', 'Hello World (Linux)' and 'Hello World (Using C libraries and Linking with gcc)' (CC BY-SA): used as a map; its examples are 32-bit (elf32, int 0x80) and were rewritten for x86-64."
search_phrases:
  - how do I assemble and run nasm code on linux
  - nasm hello world x86-64 linux
  - how to link a nasm object file with ld or gcc
  - what does nasm -f elf64 mean
  - how to write a linux system call in assembly
  - why does my assembly program segfault when it returns
---

## What you need

NASM, a linker and (optionally) a C compiler. On Debian or Ubuntu:

```bash
sudo apt install nasm binutils gcc
```

Other distributions ship the same three packages under the same names. The examples here were tested with NASM 2.16.01, GNU ld 2.40 and GCC 12.2.

## The three steps

1. **Assemble:** `nasm -f elf64 hello.asm -o hello.o` turns source into an object file. `-f elf64` selects the 64-bit Linux object format.
2. **Link:** `ld hello.o -o hello` (or `gcc hello.o -o hello` when the program uses the C library) turns object files into an executable.
3. **Run:** `./hello`, then `echo $?` to read the exit status.

## Program 1: no C library, just the kernel

This program starts at `_start` and talks to the kernel with the `syscall` instruction. The system call number goes in `rax` and the arguments in `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9` (see [the Linux calling convention](/articles/abi-system-v-linux)).

```nasm
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

section .note.GNU-stack noalloc noexec nowrite progbits
```

```bash
nasm -f elf64 hello.asm -o hello.o
ld hello.o -o hello
./hello          # Hello, doc/x86!
echo $?          # 0
```

Notes:

- `global _start` makes the entry point visible to the linker. `_start` is **not a function**: nothing called it, so it must end by calling `exit`. A `ret` there crashes the program with a segmentation fault.
- `lea rsi, [rel msg]` computes the address relative to `rip`. In the disassembly it becomes `lea rsi, [rip+0xfef]`.
- `msglen: equ $ - msg` is an assembly-time constant: the number of bytes between the label and the current position.

## Program 2: with the C library

Linking through `gcc` brings in the C runtime, which calls your `main` and supplies functions such as `puts`. Now you follow the function-calling convention: the first argument goes in `rdi`, the result in `rax`.

```nasm
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

section .note.GNU-stack noalloc noexec nowrite progbits
```

```bash
nasm -f elf64 hello_libc.asm -o hello_libc.o
gcc hello_libc.o -o hello_libc
./hello_libc     # Hello from libc
```

`gcc -no-pie hello_libc.o -o hello_libc` works too. `main` is a real function here, so it ends with `ret`; its return value becomes the exit status. The `push rbp` is there to restore 16-byte stack alignment before the `call`; without it, calls into libc may crash.

## The linker warning

Without the last line of each listing, the linker prints:

```
ld: warning: hello_libc.o: missing .note.GNU-stack section implies executable stack
ld: NOTE: This behaviour is deprecated and will be removed in a future version of the linker
```

The line `section .note.GNU-stack noalloc noexec nowrite progbits` tells the linker the program does not need an executable stack. Put it at the end of every file you assemble for Linux.

## Looking at what you built

```bash
nasm -f elf64 hello.asm -o hello.o -l hello.lst   # listing: source next to the machine code bytes
objdump -d -M intel hello                          # disassemble the finished program
nasm -f elf64 -g -F dwarf hello.asm -o hello.o     # include debug info for gdb
```

The listing shows the bytes behind each line (for example `mov eax, 1` is `B8 01 00 00 00`), which is the quickest way to learn how instructions are encoded.

## Common mistakes

- **Copying a 32-bit tutorial.** Older examples (including the Wikibooks hello-world) use `nasm -f elf32`, `int 0x80`, `ebx`/`ecx` for arguments and `write` = 4, `exit` = 1. In 64-bit code use `-f elf64`, `syscall`, and `write` = 1, `exit` = 60 with the registers above.
- **Forgetting `global _start`.** `ld` only warns (`cannot find entry symbol _start; defaulting to ...`) and starts at the beginning of `.text`, so it can seem to work and then break when you add code before `_start`.
- **Falling off the end of `_start`.** There is no caller to return to: always finish with the `exit` system call.
- **Forgetting the stack alignment** before calling C functions: see [RSP and RBP](/articles/rsp-rbp-stack-and-frame).

Related: [System V calling convention](/articles/abi-system-v-linux), [the same on Windows](/articles/nasm-windows).
