---
slug: rsp-rbp-stack-and-frame
title: "RSP and RBP: the stack pointer and the frame pointer"
summary: RSP is the hardware stack pointer behind push, pop, call and ret; RBP is only a frame pointer by convention. The standard prologue and epilogue, alignment, and the red zone.
tags: [registers, rsp, rbp, stack, functions]
status: draft
related_instructions: [push, pop, call, ret, leave, enter, lea, mov, sub]
sdm_refs:
  - "Vol. 2, PUSH (PDF pp. 1811-1814): in 64-bit mode the stack pointer is always 64 bits; push rsp pushes the old value"
  - "Vol. 2, POP (PDF pp. 1687-1691); CALL—Call Procedure (pushes the address of the following instruction; near call operand size forced to 64 bits); RET—Return From Procedure (pops the return address)"
  - "Vol. 2, LEAVE—High Level Procedure Exit ('Set RSP to RBP, then pop RBP'); ENTER—Make Stack Frame for Procedure Parameters"
extra_sources:
  - "System V AMD64 ABI draft 0.99.6, section 3.2.2 (stack frame, rsp+8 is a multiple of 16 at function entry; 128-byte red zone; footnote 7 on omitting the frame pointer)."
  - "Microsoft 'x64 stack usage' documentation: memory beyond RSP is volatile; the stack is kept 16-byte aligned outside prologs and epilogs."
  - "Example code assembled with NASM 2.16.01 and run on Linux (x86-64): frame_demo(1234) = 1234; a call to printf with a floating-point argument and a stack that is not 16-byte aligned crashed with a segmentation fault (glibc 2.36)."
search_phrases:
  - what is the difference between rsp and rbp
  - how does a stack frame work
  - what does leave do
  - what does the function prologue push rbp mov rbp rsp mean
  - why must the stack be 16-byte aligned
  - what is the red zone
---

## RSP: the stack pointer

`rsp` is special in hardware. `push` and `pop` use it, `call` pushes the return address through it, and `ret` pops that address back into `rip`. The stack grows toward lower addresses, `rsp` always points at the most recently pushed value, and in 64-bit mode it is always a full 64-bit pointer.

| Instruction | Effect on `rsp` |
|---|---|
| `push x` | `rsp -= 8`, then store |
| `pop x` | load, then `rsp += 8` |
| `call f` | push the address of the next instruction, jump to `f` |
| `ret` | pop the return address into `rip` |
| `leave` | `rsp = rbp`, then `pop rbp` |

Because `call` pushed 8 bytes, a function sees `[rsp]` = its return address on entry. Its first stack argument (if any) is above that.

## RBP: a frame pointer by convention

Nothing in the hardware forces `rbp` to hold a frame pointer, except `enter` and `leave`. The convention is useful: with `rbp` fixed at a known place in the frame, locals and arguments are addressed as `[rbp - n]` and `[rbp + n]` no matter how `rsp` moves. The standard shape:

```nasm
frame_demo:                     ; long frame_demo(long x): keep x in a local variable and read it back
        push    rbp             ; save the caller's frame pointer
        mov     rbp, rsp        ; our frame starts here
        sub     rsp, 16         ; locals; rsp stays 16-aligned because push rbp realigned it
        mov     [rbp - 8], rdi
        mov     rax, [rbp - 8]
        leave                   ; mov rsp, rbp ; pop rbp
        ret
```

Compilers often leave the frame pointer out and address locals relative to `rsp`, which frees `rbp` as an extra general-purpose register. Both are legal; the debugger-friendly choice is to keep it.

## Alignment: a rule of the ABI, enforced by crashes

The hardware does not require an aligned stack, but both calling conventions do: **`rsp` must be a multiple of 16 immediately before a `call`**. Since `call` pushes 8 bytes, that means `rsp` is 8 modulo 16 when a function is entered, and a function that calls others must fix that up (a single `push rbp` does it, as above, or `sub rsp, 8`). Library code is entitled to rely on it. On Linux a call to `printf` with a floating-point argument and a misaligned stack crashed with a segmentation fault.

## Below RSP

- **Linux (System V):** the 128 bytes just below `rsp` are the **red zone**: signal and interrupt handlers do not touch them, so a leaf function may keep its locals there without moving `rsp`. Do not use it in a function that makes calls, since the `call` overwrites it.
- **Windows:** there is no red zone. Everything below `rsp` may be overwritten at any moment, so reserve space with `sub rsp, n` before using it.

## Gotchas

- `push rsp` stores the value `rsp` had *before* the push, and `pop rsp` loads `rsp` from the stack.
- Unbalanced `push`/`pop` pairs shift every later `[rsp + n]` reference and corrupt the return address.
- `lea rsp, [rsp + n]` and `add rsp, n` both release stack space; `lea` does not change the flags.

Related: [Calling convention on Linux](/articles/abi-system-v-linux) and [on Windows](/articles/abi-microsoft-x64-windows).
