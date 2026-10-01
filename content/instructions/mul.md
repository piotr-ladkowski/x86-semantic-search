---
slug: mul
mnemonic: MUL
aliases: []
title: Unsigned Multiply
summary: Multiplies RAX by the operand as unsigned numbers and stores the 128-bit product in RDX:RAX.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["MUL—Unsigned Multiply"]
extra_sources: []
flags:
  modified: [OF, CF]
  undefined: [SF, ZF, AF, PF]
  note: "CF and OF are 0 if the upper half of the product is 0, otherwise 1."
forms:
  - {syntax: "MUL r/m64", opcode: "REX.W + F7 /4", note: "RDX:RAX := RAX * r/m64. The 32-bit form (F7 /4) multiplies EAX and writes EDX:EAX; the 8-bit form (F6 /4) multiplies AL and writes AX."}
search_phrases:
  - multiply two unsigned integers
  - full double-width product of two 64-bit numbers
  - get the high half of a multiplication
  - multiply and keep both halves of the result
  - detect unsigned multiplication overflow
related: [imul, mulx, div, adc, shl]
---

## What it does

`mul src` multiplies the unsigned value in `rax` by `src` (a register or memory operand) and stores the full 128-bit product in `rdx:rax`: the low 64 bits in `rax`, the high 64 bits in `rdx`. The multiplicand is implicit, so there is only one explicit operand.

## When to use it

- Multiplying unsigned numbers when you need the whole product, for example 64x64 -> 128 bit arithmetic or big-number code.
- Checking for unsigned overflow of a 64-bit multiply: CF and OF are set when `rdx` is non-zero.
- For an ordinary signed or truncated multiply, `imul` is simpler (it has two- and three-operand forms). For a multiply that leaves the flags alone and lets you choose both destination registers, see `mulx` (BMI2); note that it still takes `rdx` as its implicit multiplicand.

## Gotchas

- **Implicit registers.** `rax` is always the multiplicand and `rdx` is always overwritten by the high half, even if you only wanted the low half. Save anything you need from `rdx` first.
- **No immediate operand.** `mul 10` is not valid; load the constant into a register.
- **Only CF and OF mean anything.** SF, ZF, AF and PF are undefined afterwards, so do not branch on them.
- **32-bit form.** `mul ecx` multiplies `eax` and writes `edx:eax`; both writes zero-extend into `rdx` and `rax`. The 8-bit form writes the 16-bit product to `ax`.
- It is unsigned: for signed values the high half is wrong. Use `imul` (one-operand form) instead.

## Example

```nasm
mov  rax, 0xFFFFFFFFFFFFFFFF
mov  rbx, 2
mul  rbx                ; rdx:rax = 0x1:FFFFFFFFFFFFFFFE, CF = OF = 1 (rdx != 0)

mul  qword [rdi]        ; rdx:rax = rax * the qword at [rdi]
```
