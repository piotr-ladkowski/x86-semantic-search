---
slug: shl
mnemonic: SHL
aliases: [SAL]
title: Shift Left
summary: Shifts the bits of the operand toward the high end, filling with zeros; equivalent to multiplying by a power of two.
category: shift-rotate
status: draft
cpuid_feature: null
sdm_entries: ["SAL/SAR/SHL/SHR—Shift"]
extra_sources: []
flags:
  modified: [CF, OF, SF, ZF, PF]
  undefined: [AF]
  note: "If the count is 0 no flag changes. CF is the last bit shifted out. OF is defined only for 1-bit shifts (set if the top two bits of the original value differed) and is undefined otherwise. AF is undefined for a non-zero count."
forms:
  - {syntax: "SHL r/m64, imm8", opcode: "REX.W + C1 /4 ib", note: "SAL is the same instruction and the same opcode. The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "SHL r/m64, CL", opcode: "REX.W + D3 /4", note: "Count in CL. Masked to 6 bits for a 64-bit operand (5 bits for 8-, 16- and 32-bit operands)."}
  - {syntax: "SHL r/m64, 1", opcode: "REX.W + D1 /4", note: "Short encoding for a shift by one."}
search_phrases:
  - shift bits to the left
  - multiply by a power of two
  - double a number
  - move a bit field into position
  - shift left by a variable amount
related: [shr, sar, rol, shld, shlx, imul, lea]
---

## What it does

`shl dst, count` moves every bit of `dst` toward the most significant end by `count` positions and fills the vacated low bits with zeros. Bits shifted out of the top are discarded, except that the **last one shifted out is kept in CF**. Shifting left by *n* multiplies by 2^n (modulo the operand size). `sal` is just another name for the same instruction.

## When to use it

- Multiplying by a power of two: `shl rax, 3` multiplies by 8.
- Moving a bit field into position before combining it with `or`.
- Building masks: `mov eax, 1` then `shl eax, cl` gives a value with only bit `cl` set.

## Gotchas

- **The count is masked.** It is reduced to its low 6 bits for a 64-bit operand (5 bits for 32-bit and smaller), so `shl rax, 64` shifts by 0, and a count of 65 in `cl` shifts by 1. This is not "shift everything out".
- **A count of 0 changes nothing,** including the flags. After a variable-count shift (`cl`) the flags depend on the count, so do not rely on them unless the count is known to be non-zero.
- **CF and OF are fiddly.** CF holds the last bit shifted out; OF is only defined for a shift by exactly 1, otherwise it is undefined.
- **Overflow is silent.** Bits that move past the top are lost; nothing traps. For signed or checked multiplication use `imul`.
- **The count is an 8-bit immediate, the constant 1, or `cl`.** No other register can supply the count (see `shlx` for that).
- **32-bit operations zero the upper half** of the register (`shl eax, 4` clears bits 63:32 of `rax`).
- A `lock` prefix is invalid (`#UD`).

## Example

```nasm
shl  rax, 3            ; rax *= 8
shl  rdx, 1            ; double rdx; CF = the old top bit
mov  ecx, 5
mov  eax, 1
shl  eax, cl           ; eax = 1 << 5 = 32 (rax upper half is zero)
```
