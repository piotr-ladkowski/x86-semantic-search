---
slug: idiv
mnemonic: IDIV
aliases: []
title: Signed Divide
summary: Divides the signed value in RDX:RAX by the operand; the quotient goes to RAX and the remainder to RDX.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["IDIV—Signed Divide"]
extra_sources: []
flags:
  undefined: [CF, OF, SF, ZF, AF, PF]
  note: "All six status flags are undefined afterwards. Errors are reported by the #DE exception, not by a flag."
forms:
  - {syntax: "IDIV r/m64", opcode: "REX.W + F7 /7", note: "RAX := quotient, RDX := remainder of RDX:RAX / r/m64. The 32-bit form (F7 /7) divides EDX:EAX; the 8-bit form divides AX into AL and AH."}
search_phrases:
  - divide two signed integers
  - signed division
  - remainder of a signed division
  - divide a negative number
  - integer division that rounds toward zero
related: [div, imul, cqo, cdqe, neg]
---

## What it does

`idiv src` divides the signed 128-bit value in `rdx:rax` by `src` (a register or memory operand). The quotient is stored in `rax` and the remainder in `rdx`. The quotient is truncated toward zero, so a non-zero remainder has the same sign as the dividend (-7 divided by 2 gives quotient -3 and remainder -1).

## When to use it

- Signed integer division and modulo in one step.
- Dividing a signed value wider than 64 bits by a 64-bit divisor.

## Gotchas

- **Sign-extend the dividend, do not zero it.** Put the value in `rax` and run `cqo` to copy its sign into `rdx`. Zeroing `rdx` with `xor edx, edx` turns a negative dividend into a huge positive one.
- **`#DE` (divide error) is raised** when the divisor is zero **or** when the quotient does not fit in `rax`. The classic case is the most negative 64-bit number divided by -1: the true quotient is 2^63, which does not fit.
- **Fixed registers.** `rax` and `rdx` hold the dividend and results, and `rdx` is overwritten.
- **No immediate divisor.** Load constants into a register.
- **Flags are undefined,** so do not branch on them after `idiv`.
- A `lock` prefix is invalid (`#UD`).

## Example

```nasm
mov  rax, -7
cqo                    ; rdx:rax = -7 sign-extended to 128 bits
mov  rcx, 2
idiv rcx               ; rax = -3 (quotient), rdx = -1 (remainder)
```
