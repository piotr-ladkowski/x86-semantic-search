---
slug: test
mnemonic: TEST
aliases: []
title: Logical Compare
summary: ANDs the two operands to set the flags and discards the result; test reg, reg checks for zero.
category: bit-byte
status: draft
cpuid_feature: null
sdm_entries: ["TEST—Logical Compare"]
extra_sources: []
flags:
  modified: [OF, CF, SF, ZF, PF]
  undefined: [AF]
  note: "OF and CF are cleared; SF, ZF and PF are set from the AND result. No operand is written."
forms:
  - {syntax: "TEST r/m64, r64", opcode: "REX.W + 85 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "TEST r/m64, imm32", opcode: "REX.W + F7 /0 id", note: "imm32 is sign-extended to 64 bits."}
search_phrases:
  - check whether a register is zero
  - is a particular bit on or off
  - check whether any bit of a mask is set
  - bitwise and without storing the result
  - check the sign of a number
related: [cmp, and, jcc, setcc, bt]
---

## What it does

`test a, b` computes `a AND b`, sets the flags from the result, and discards it. Neither operand changes. Afterwards **ZF** is set if no bit was in common (the AND was zero), **SF** holds the top bit of the result, and **PF** the parity of its low byte.

## When to use it

- Checking whether a value is zero or negative: `test rax, rax` then `jz` / `js`.
- Checking whether any of several bits are set: `test eax, 0x30`.
- Reading one flag bit out of a status word without disturbing it: `test byte [rdi], 1`.

## Gotchas

- **`test r, r` is the idiom for "is it zero?".** ANDing a value with itself leaves it unchanged, so ZF reports whether it was 0; it is also a byte shorter than `cmp r, 0`.
- **ZF means "none of those bits were set"**, which is the opposite of what a quick read suggests: `jnz` after `test` is taken when at least one of the tested bits is set.
- **CF and OF are always cleared,** so `jc`/`jo` after a `test` never fire, and `AF` is undefined.
- **Immediates are sign-extended** for 64-bit operands, so a 64-bit `test` cannot isolate bit 31 with an immediate (it would also test every bit above it). Use a 32-bit register, `test eax, 0x80000000`, or `bt`.
- **A `lock` prefix is invalid** (`#UD`); `test` never writes.

## Example

```nasm
test rax, rax          ; ZF=1 if rax == 0; SF=1 if rax is negative
jz   .is_zero

test eax, 0x30         ; are bit 4 or bit 5 set?
jnz  .some_set

test byte [rdi], 1     ; look at the lowest bit of a byte in memory
```
