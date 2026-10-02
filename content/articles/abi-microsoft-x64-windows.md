---
slug: abi-microsoft-x64-windows
title: "Calling convention on Windows: the Microsoft x64 ABI"
summary: Which registers carry arguments, why the caller must reserve 32 bytes of shadow space, which registers a function must preserve, and how it differs from Linux. Verified with real programs.
tags: [calling-convention, abi, windows, microsoft-x64]
status: draft
related_instructions: [call, ret, push, pop, lea, mov, sub]
sdm_refs:
  - "Vol. 2, CALL—Call Procedure and RET—Return From Procedure: near call pushes the return address, near branches use 64-bit operand size in 64-bit mode"
extra_sources:
  - "Microsoft Learn, 'x64 Calling Convention' (learn.microsoft.com/en-us/cpp/build/x64-calling-convention): argument registers, shadow store, return values, volatile and nonvolatile register lists, varargs."
  - "Microsoft Learn, 'x64 stack usage' (learn.microsoft.com/en-us/cpp/build/stack-usage): home space, 16-byte alignment, memory beyond RSP is volatile."
  - "Observed with MinGW-w64 GCC 12 (-O1 -S) and NASM 2.16.01: arguments in ecx/edx/r8d/r9d for 32-bit long, first stack argument at [rsp+40] on entry, push rdi/rsi in a function that keeps values across a call, no use of memory below rsp. Functions add3, sum5, keep_rsi and say_answer assembled with nasm -f win64, linked with MinGW-w64 gcc and run under Wine 8.0: add3(1,2,3) = 6, sum5(1..5) = 15, printf output correct. Not run on real Windows."
  - "Wikibooks, 'x86 Assembly/Print Version', section 'Hello World (Using only Win32 system calls)' (CC BY-SA): a 32-bit stdcall example, not applicable to x64."
search_phrases:
  - which registers pass arguments on windows x64
  - what is shadow space in the windows calling convention
  - which registers must be preserved on windows x64
  - how do I call a windows api function from assembly
  - difference between linux and windows x86-64 calling conventions
  - why does long have a different size on windows
---

64-bit Windows has one default calling convention (no `cdecl`/`stdcall` split as on 32-bit x86). It is a software agreement, not part of the CPU. For Linux see [the System V convention](/articles/abi-system-v-linux).

## Arguments

| What | Where |
|---|---|
| Integer and pointer arguments 1 to 4 | `rcx`, `rdx`, `r8`, `r9` |
| Floating-point arguments 1 to 4 | `xmm0` ... `xmm3` |
| Argument 5 and later | On the stack, right to left, 8-byte aligned slots |

Registers are assigned by **position**, not by type: the 2nd argument is `rdx` if it is an integer, `xmm1` if it is a float, and the register for the other type is simply unused. Anything that is not 1, 2, 4 or 8 bytes wide is passed by pointer.

## Shadow space

The caller **always** reserves 32 bytes (room for four 8-byte values) on the stack, immediately above the return address, even when the callee takes fewer than four arguments. The callee owns that space and may spill its register arguments there, or use it as scratch. It follows that the first stack argument sits at **`[rsp + 40]`** on entry: 8 bytes of return address plus 32 of shadow space.

```nasm
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
```

## Return values

An integer or pointer that fits in 64 bits is returned in `rax`; a float, double or vector in `xmm0`. A structure that is not 1, 2, 4 or 8 bytes wide is returned through a caller-allocated buffer whose address is passed as a hidden **first argument in `rcx`** (shifting the others along); the callee returns that address in `rax`.

## Preserved and scratch registers

| Preserved by the callee (nonvolatile) | Free for the callee to destroy (volatile) |
|---|---|
| `rbx`, `rbp`, **`rdi`**, **`rsi`**, `rsp`, `r12` ... `r15`, **`xmm6` ... `xmm15`** | `rax`, `rcx`, `rdx`, `r8` ... `r11`, `xmm0` ... `xmm5` |

The bold entries are what differs from Linux: `rdi`, `rsi` and `xmm6`-`xmm15` must survive a call on Windows, while Linux treats them as scratch.

```nasm
keep_rsi:                       ; rsi and rdi are callee-saved on Windows (not on Linux)
        push    rsi
        mov     rsi, rcx
        mov     rax, rsi
        pop     rsi
        ret
```

## The stack

- **Alignment:** `rsp` must be 16-byte aligned except inside a prologue or epilogue, so it is 8 modulo 16 on entry. A function that calls others therefore subtracts **32 bytes of shadow space plus 8 bytes for each stack argument it passes, rounded so the total is 8 modulo 16**. With no or one stack argument that is `sub rsp, 40`; with two it is `sub rsp, 56`. It ends with the matching `add`.
- **No red zone:** memory below `rsp` may be overwritten at any time, so move `rsp` first.

## Calling C and Windows API functions

```nasm
say_answer:                     ; void say_answer(void): printf("answer = %d\n", 42)
        sub     rsp, 40         ; 32-byte shadow space + 8 to realign (rsp is 8 mod 16 on entry)
        lea     rcx, [fmt]      ; 1st argument: rcx
        mov     edx, 42         ; 2nd argument: rdx
        call    printf
        add     rsp, 40
        ret
```

For `WriteFile(hFile, buf, len, &written, NULL)` the fifth argument goes at `[rsp + 32]`, right above the shadow space, which is why the [NASM-on-Windows guide](/articles/nasm-windows) reserves 40 bytes (32 + 8 for that argument): this also leaves `rsp` aligned.

For variadic functions, floating-point arguments must be copied into the matching integer register as well as the `xmm` register.

## Types

`int` and `long` are both 32 bits on 64-bit Windows; `long long` and pointers are 64 bits. On Linux `long` is 64 bits. (The compiler output used `ecx` and `edx` for `long` arguments.)

## Gotchas

- **Forgetting the shadow space:** the callee may write into those 32 bytes, silently overwriting whatever you stored at `[rsp]` to `[rsp + 31]`.
- **Using `rdi`/`rsi` freely:** harmless on Linux, but corrupts the caller on Windows unless you save them.
- **32-bit examples:** the stack-passed arguments, `stdcall` names such as `_GetStdHandle@4` and `-f win32` you find in older tutorials do not apply to x64.
- **Direct `syscall`:** Windows programs call the DLL functions (`kernel32.dll` and friends) rather than using the `syscall` instruction as Linux programs do.
