---
slug: abi-system-v-linux
title: "Calling convention on Linux: the System V AMD64 ABI"
summary: Which registers carry arguments and results, which registers a function must preserve, how the stack must be aligned, and the separate rules for system calls. Verified with real programs.
tags: [calling-convention, abi, linux, system-v]
status: draft
related_instructions: [call, ret, push, pop, syscall, lea, mov]
sdm_refs:
  - "Vol. 2, SYSCALL—Fast System Call: RCX receives the address of the next instruction, R11 receives RFLAGS"
  - "Vol. 2, CALL—Call Procedure and RET—Return From Procedure: near call pushes the return address, near branches use 64-bit operand size in 64-bit mode"
extra_sources:
  - "System V Application Binary Interface, AMD64 Architecture Processor Supplement, draft version 0.99.6 (2012): section 3.2.1 (registers, DF), 3.2.2 (stack frame, red zone, alignment), 3.2.3 (parameter passing, returning of values, %al for variadic calls), Appendix A.2 (Linux kernel system call conventions)."
  - "Observed with GCC 12.2 (-O1 -S) and NASM 2.16.01 on Debian 12: argument registers, pushes of rbx/rbp/r12-r15 in a function that keeps values across a call, and use of memory below rsp in a leaf function. Test functions add3, sum7, keep_rbx and say_answer assembled, linked with gcc and run: add3(1,2,3) = 6, sum7(1..7) = 28, printf output correct; a misaligned call to printf with a floating-point argument segfaulted."
  - "Wikibooks, 'x86 Assembly/Print Version', section 'C Calling Conventions' (CC BY-SA): covers 32-bit cdecl only, so it is not used for the 64-bit rules."
search_phrases:
  - which registers are used to pass arguments on linux x86-64
  - what is the system v calling convention
  - which registers must a function preserve
  - how do I call printf from assembly on linux
  - what is the red zone
  - how are system call arguments passed on linux
---

This is the convention used by Linux and most other Unix-like systems on x86-64. It is a software agreement, not part of the CPU: the Intel manual says nothing about it. For Windows see [the Microsoft x64 convention](/articles/abi-microsoft-x64-windows).

## Arguments

| What | Where |
|---|---|
| Integer and pointer arguments 1 to 6 | `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` |
| Floating-point arguments 1 to 8 | `xmm0` ... `xmm7` |
| Everything beyond that | On the stack, pushed right to left; each takes an 8-byte slot |

The first stack argument is therefore at `[rsp + 8]` when the callee starts (the return address is at `[rsp]`), the next at `[rsp + 16]`, and so on. There is **no shadow space** (that is a Windows feature). Integer and floating-point arguments count separately: the 2nd integer argument is `rsi` whether or not floating-point arguments come before it.

```nasm
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
```

## Return values

- Integer or pointer: `rax`; a 128-bit integer uses `rax` and `rdx`.
- Floating-point: `xmm0` (and `xmm1` for a second one).
- A struct too large for registers: the caller allocates the space and passes its address as a hidden **first argument in `rdi`**, shifting the real arguments along; the callee returns that address in `rax`.

## Preserved and scratch registers

| Preserved by the callee (callee-saved) | Free for the callee to destroy (caller-saved) |
|---|---|
| `rbx`, `rbp`, `r12`, `r13`, `r14`, `r15` (and `rsp`) | `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8` ... `r11`, all `xmm` registers |

A function that wants to use a preserved register saves it first and restores it before returning, as a compiler's prologue shows (`push r15 ... push rbx`). The direction flag must be **clear** on entry and return.

```nasm
keep_rbx:                       ; long keep_rbx(long x): uses rbx, so it must save and restore it
        push    rbx
        mov     rbx, rdi
        mov     rax, rbx
        pop     rbx
        ret
```

If a *caller* needs a scratch register's value to survive a call, it must save it itself (in a preserved register or on the stack).

## The stack

- **Alignment:** `rsp` must be a multiple of 16 immediately before a `call`. Because `call` pushes the 8-byte return address, `rsp` is 8 modulo 16 inside the callee until it pushes something. A misaligned call can crash: a call to `printf` with a floating-point argument segfaulted in testing.
- **Red zone:** the 128 bytes below `rsp` may be used by a leaf function without adjusting `rsp`; interrupt and signal handlers leave them alone. A function that calls others must not rely on it.

## Calling C library functions

Variadic functions such as `printf` also need `al` set to the number of vector registers used (0 here):

```nasm
say_answer:                     ; void say_answer(void): printf("answer = %d\n", 42)
        push    rbp             ; entry rsp is 8 mod 16; this push makes it 16-aligned for the call
        lea     rdi, [fmt]      ; 1st argument: the format string
        mov     esi, 42         ; 2nd argument: the value for %d
        xor     eax, eax        ; al = number of vector registers used: none (printf is variadic)
        call    printf wrt ..plt
        pop     rbp
        ret
```

## System calls are a different convention

The `syscall` instruction talks to the kernel, not to a function, and uses its own register assignment:

| What | Where |
|---|---|
| System call number | `rax` |
| Arguments 1 to 6 | `rdi`, `rsi`, `rdx`, **`r10`**, `r8`, `r9` |
| Result | `rax`: a value from -4095 to -1 means an error (it is `-errno`) |
| Destroyed | `rcx` and `r11` (the CPU stores the return address and flags there) |

Note `r10` where a function call would use `rcx`. No system call takes more than six arguments, and none passes anything on the stack. See [the NASM-on-Linux guide](/articles/nasm-linux) for a complete `write` + `exit` program.

## Types

On Linux, `int` is 32 bits, while `long` and pointers are 64 bits. On Windows `long` is only 32 bits, which matters when assembly meets C declarations written for the other system.

## Gotchas

- Forgetting to preserve `rbx`, `rbp` or `r12`-`r15` corrupts the *caller's* variables, usually far from the actual bug.
- 32-bit tutorials (including most of the Wikibooks examples) pass arguments on the stack and use `int 0x80`; none of that applies in 64-bit code.
- In a direct `syscall`, `rcx` and `r11` are destroyed and the fourth argument goes in `r10`. If you instead call a libc wrapper such as `write` as an ordinary function, the normal function rules apply (arguments in `rdi`, `rsi`, `rdx`, `rcx`, ...) and libc takes care of the system call.
