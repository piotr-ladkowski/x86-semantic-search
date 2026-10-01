---
slug: nasm-windows
title: "Assemble, link and run a NASM program on Windows"
summary: Assemble with nasm -f win64, link with MinGW-w64 (tested) or Microsoft's linker, and run. Two programs, one with the C runtime and one with only kernel32, and what was and was not verified.
tags: [nasm, windows, toolchain, tutorial]
status: draft
related_instructions: [call, ret, lea, mov, sub, xor, push]
sdm_refs: []
extra_sources:
  - "Verified: both programs assembled with NASM 2.16.01 using 'nasm -f win64', linked with MinGW-w64 GCC 12 on Linux (x86_64-w64-mingw32-gcc) and run under Wine 8.0, printing the expected text and exiting with status 0. NOT verified: running on real Windows, the Microsoft linker (link.exe) and GoLink; those command lines are standard usage but were not run."
  - "Microsoft Learn, 'x64 Calling Convention' and 'x64 stack usage': shadow space, argument registers, alignment."
  - "Wikibooks, 'x86 Assembly/Print Version', section 'Hello World (Using only Win32 system calls)' (CC BY-SA): used as a map; that example is 32-bit (-f win32, stdcall names like _GetStdHandle@4, arguments pushed on the stack) and was rewritten for x64."
search_phrases:
  - how do I assemble and run nasm code on windows
  - nasm hello world x64 windows
  - how to link a nasm object file on windows
  - what does nasm -f win64 mean
  - how to call a windows api function from nasm
  - how to call printf from assembly on windows
---

## What you need

1. **NASM for Windows**, from the NASM website (installer or zip). Check it with `nasm -v`.
2. **A linker.** Pick one:
   - **MinGW-w64 / MSYS2 `gcc`** (the route tested for this article). It also supplies the C runtime start-up code.
   - **Microsoft's linker** (`link.exe`), installed with the Visual Studio Build Tools; run it from the "x64 Native Tools Command Prompt".
   - **GoLink**, a small standalone linker popular with assembly programmers.

Remember that Windows uses a different [calling convention](/articles/abi-microsoft-x64-windows) from Linux: arguments in `rcx`, `rdx`, `r8`, `r9` and a 32-byte shadow space.

## The steps

1. **Assemble:** `nasm -f win64 hello_win.asm -o hello_win.obj`. `-f win64` selects the 64-bit Windows (COFF) object format.
2. **Link:** see the two programs below.
3. **Run:** `hello_win.exe`, then `echo %ERRORLEVEL%` in `cmd.exe` (or `$LASTEXITCODE` in PowerShell) for the exit code.

## Program 1: using the C runtime

Linking through `gcc` provides the start-up code that calls your `main`, and `puts` comes from the C library.

```nasm
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
```

```bat
nasm -f win64 hello_win.asm -o hello_win.obj
gcc hello_win.obj -o hello_win.exe
hello_win.exe
```

(The tested build used the cross-compiler spelled `x86_64-w64-mingw32-gcc`; on Windows with MinGW-w64 or MSYS2 the compiler is invoked as `gcc`.) `sub rsp, 40` is the standard pattern: 32 bytes of shadow space the callee may use, plus 8 bytes to bring `rsp` back to a multiple of 16.

## Program 2: only the Windows API, no C runtime

This version calls three functions from `kernel32.dll` directly. There is no `main`; the entry point is `start`, and the program must end by calling `ExitProcess`.

```nasm
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
```

Link with the tested MinGW-w64 command:

```bat
nasm -f win64 hello_win32.asm -o hello_win32.obj
gcc -nostdlib -o hello_win32.exe hello_win32.obj -lkernel32 -Wl,-e,start -Wl,--subsystem,console
hello_win32.exe
```

`-nostdlib` leaves out the C runtime, `-lkernel32` supplies the three functions, `-e start` names the entry point, and `--subsystem,console` makes it a console program.

The equivalent lines for the other linkers are the usual ones but were **not run** while writing this article:

```bat
link /subsystem:console /entry:start /nodefaultlib hello_win32.obj kernel32.lib
golink /console /entry start hello_win32.obj kernel32.dll
```

Use the Win32-only program as your starting point when linking with `link.exe`: it avoids having to name the C-runtime libraries.

## How the Win32 call works

- `GetStdHandle(-11)` returns the handle for standard output in `rax`.
- `WriteFile` takes five arguments: four in `rcx`, `rdx`, `r8`, `r9` and the **fifth on the stack at `[rsp + 32]`**, directly above the shadow space. That is why the program reserves 40 bytes: 32 + 8, which also keeps `rsp` aligned.
- Names carry no decoration on x64. Older 32-bit examples import `_GetStdHandle@4`; here it is just `GetStdHandle`.
- `13, 10` is the Windows line ending (carriage return, line feed).

## Common mistakes

- **Copying a 32-bit tutorial.** `-f win32`, arguments pushed with `push`, and `@N` suffixes belong to 32-bit x86 and do not work in a `win64` object.
- **No shadow space:** callees may write to those 32 bytes and overwrite your data.
- **Misaligned stack** at a `call`: it must be a multiple of 16.
- **Returning from `start`:** there is no caller; end with `ExitProcess`.
- **WSL is Linux.** A program run inside the Windows Subsystem for Linux is a Linux program: follow [the Linux guide](/articles/nasm-linux) there.

Related: [the same on Linux](/articles/nasm-linux).
