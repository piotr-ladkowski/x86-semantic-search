---
slug: sar
mnemonic: SAR
aliases: []
title: Shift Arithmetic Right
summary: Shifts the operand toward the low end, copying the sign bit into the vacated bits; signed division by a power of two.
category: shift-rotate
status: draft
cpuid_feature: null
sdm_entries: ["SAL/SAR/SHL/SHR—Shift"]
extra_sources: []
flags:
  modified: [CF, OF, SF, ZF, PF]
  undefined: [AF]
  note: "If the count is 0 no flag changes. CF is the last bit shifted out. OF is cleared for 1-bit shifts and undefined otherwise. AF is undefined for a non-zero count."
forms:
  - {syntax: "SAR r/m64, imm8", opcode: "REX.W + C1 /7 ib", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "SAR r/m64, CL", opcode: "REX.W + D3 /7", note: "Count in CL. Masked to 6 bits for a 64-bit operand (5 bits for 8-, 16- and 32-bit operands)."}
  - {syntax: "SAR r/m64, 1", opcode: "REX.W + D1 /7", note: "Short encoding for a shift by one."}
search_phrases:
  - arithmetic shift right keeping the sign
  - divide a signed number by a power of two
  - shift right and preserve the sign bit
  - fill a register with copies of the sign bit
related: [shr, shl, idiv, cqo, sarx]
---

## What it does

`sar dst, count` moves every bit of `dst` toward the least significant end by `count` positions, and fills the vacated high bits with copies of the **original sign bit**. Positive numbers behave like `shr`; negative numbers stay negative. The last bit shifted out is kept in CF.

## When to use it

- Dividing a signed number by a power of two: `sar rax, 3` divides by 8.
- Turning a sign into a mask: `sar rax, 63` gives 0 for a non-negative value and -1 (all ones) for a negative one.
- Sign-extending within a register after shifting a field into the top bits.

## Gotchas

- **It rounds toward negative infinity, not toward zero.** `idiv` truncates toward zero, so the two disagree for negative numbers that do not divide evenly: dividing -9 by 4 gives -2 with `idiv`, but `sar` by 2 gives -3. The SDM calls this out; keep it in mind when replacing a division by a shift.
- **The count is masked** to its low 6 bits for a 64-bit operand (5 bits for 32-bit and smaller), so `sar rax, 64` shifts by 0.
- **A count of 0 changes nothing,** including the flags.
- **OF is cleared for 1-bit shifts** and undefined for other counts; CF is the last bit shifted out.
- **The count is an 8-bit immediate, the constant 1, or `cl`.** No other register can supply the count (see `sarx`).
- **32-bit operations zero the upper half** of the register, and the sign bit used is bit 31, not bit 63.
- A `lock` prefix is invalid (`#UD`).

## Example

```nasm
sar  rax, 1            ; signed rax / 2, rounded toward negative infinity
sar  rax, 63           ; rax = 0 if rax >= 0, else -1

mov  rax, -9
sar  rax, 2            ; rax = -3 (idiv by 4 would give -2)
```
