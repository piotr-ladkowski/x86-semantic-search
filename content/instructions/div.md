---
slug: div
mnemonic: DIV
aliases: []
title: Unsigned Divide
summary: Divides the unsigned value in RDX:RAX by the operand; the quotient goes to RAX and the remainder to RDX.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["DIV—Unsigned Divide"]
extra_sources: []
flags:
  undefined: [CF, OF, SF, ZF, AF, PF]
  note: "All six status flags are undefined afterwards. Errors are reported by the #DE exception, not by a flag."
forms:
  - {syntax: "DIV r/m64", opcode: "REX.W + F7 /6", note: "RAX := quotient, RDX := remainder of RDX:RAX / r/m64. The 32-bit form (F7 /6) divides EDX:EAX; the 8-bit form divides AX into AL (quotient) and AH (remainder)."}
search_phrases:
  - divide two unsigned integers
  - get the remainder of a division
  - unsigned division
  - modulo operation
  - integer division with quotient and remainder
related: [idiv, mul, cqo, shr, xor]
---

## What it does

`div src` divides the 128-bit unsigned value in `rdx:rax` (the dividend) by `src` (a register or memory operand, the divisor). The quotient is stored in `rax` and the remainder in `rdx`. The result is truncated toward zero and the remainder is always smaller than the divisor.

## When to use it

- Unsigned integer division and modulo in one step: you get both the quotient and the remainder.
- Dividing a value wider than 64 bits by a 64-bit divisor.
- For a power-of-two divisor, `shr` gives the same unsigned quotient and `and` the same remainder, with no register setup.

## Gotchas

- **Set up `rdx` first.** The dividend is `rdx:rax`, so for a plain 64-bit value zero the upper half with `xor edx, edx` before dividing. Leftover garbage in `rdx` changes the dividend.
- **`#DE` (divide error) is raised** when the divisor is zero **or** when the quotient does not fit in `rax` (for instance when `rdx` is greater than or equal to the divisor). That is a fault, not a flag, so there is nothing to test afterwards.
- **Fixed registers.** `rax` and `rdx` are always the dividend and results, and `rdx` is overwritten even if you only want the quotient.
- **No immediate divisor.** Load constants into a register.
- **Flags are undefined,** so do not branch on them after `div`.
- A `lock` prefix is invalid (`#UD`).

## Example

```nasm
mov  rax, 100
xor  edx, edx          ; upper half of the dividend = 0
mov  rcx, 7
div  rcx               ; rax = 14 (quotient), rdx = 2 (remainder)

div  qword [rdi]       ; divide rdx:rax by the qword at [rdi]
```
