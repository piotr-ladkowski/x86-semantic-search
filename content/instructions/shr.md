---
slug: shr
mnemonic: SHR
aliases: []
title: Shift Right (Logical)
summary: Shifts the bits of the operand toward the low end, filling with zeros; equivalent to unsigned division by a power of two.
category: shift-rotate
status: draft
cpuid_feature: null
sdm_entries: ["SAL/SAR/SHL/SHR—Shift"]
extra_sources: []
flags:
  modified: [CF, OF, SF, ZF, PF]
  undefined: [AF]
  note: "If the count is 0 no flag changes. CF is the last bit shifted out. OF is defined only for 1-bit shifts, where it is set to the top bit of the original value, and is undefined otherwise. AF is undefined for a non-zero count."
forms:
  - {syntax: "SHR r/m64, imm8", opcode: "REX.W + C1 /5 ib", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "SHR r/m64, CL", opcode: "REX.W + D3 /5", note: "Count in CL. Masked to 6 bits for a 64-bit operand (5 bits for 8-, 16- and 32-bit operands)."}
  - {syntax: "SHR r/m64, 1", opcode: "REX.W + D1 /5", note: "Short encoding for a shift by one."}
search_phrases:
  - shift bits to the right filling with zeros
  - divide an unsigned number by a power of two
  - logical shift right
  - extract the high bits of a value
  - halve an unsigned value
related: [shl, sar, ror, shrd, shrx, div, and]
---

## What it does

`shr dst, count` moves every bit of `dst` toward the least significant end by `count` positions and fills the vacated high bits with **zeros**. The last bit shifted out is kept in CF. For unsigned values, shifting right by *n* divides by 2^n and rounds down.

## When to use it

- Dividing an unsigned number by a power of two: `shr rax, 4` divides by 16.
- Extracting the top bits of a value: `shr rax, 56` leaves the highest byte.
- Reading a single bit position: `shr rax, 63` leaves the top bit as 0 or 1.

## Gotchas

- **Zero fill means unsigned.** For a negative signed number `shr` produces a huge positive value, so use `sar` for signed values.
- **The count is masked** to its low 6 bits for a 64-bit operand (5 bits for 32-bit and smaller), so `shr rax, 64` shifts by 0, not by "everything".
- **A count of 0 changes nothing,** including the flags. After a variable-count shift the flags depend on the count.
- **OF is only defined for a shift by exactly 1** (then it is the original top bit); CF is the last bit shifted out.
- **The count is an 8-bit immediate, the constant 1, or `cl`.** No other register can supply the count (see `shrx`).
- **32-bit operations zero the upper half** of the register.
- A `lock` prefix is invalid (`#UD`).

## Example

```nasm
shr  rax, 4            ; rax /= 16 (unsigned)
shr  rax, 63           ; rax = the old top bit (0 or 1)
shr  rdx, cl           ; variable shift; count masked to 6 bits
```
