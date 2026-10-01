---
slug: movsx
mnemonic: MOVSX
aliases: [MOVSXD]
title: Move With Sign-Extension
summary: Copies a byte, word or doubleword into a larger register, filling the upper bits with copies of the sign bit.
category: data-transfer
status: draft
cpuid_feature: null
sdm_entries: ["MOVSX/MOVSXD—Move With Sign-Extension"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "MOVSX r64, r/m8", opcode: "REX.W + 0F BE /r"}
  - {syntax: "MOVSX r64, r/m16", opcode: "REX.W + 0F BF /r"}
  - {syntax: "MOVSXD r64, r/m32", opcode: "REX.W + 63 /r", note: "The only way to sign-extend a doubleword into a quadword."}
  - {syntax: "MOVSX r32, r/m8", opcode: "0F BE /r", note: "Also zeroes bits 63:32 of the 64-bit register."}
  - {syntax: "MOVSX r32, r/m16", opcode: "0F BF /r", note: "Also zeroes bits 63:32 of the 64-bit register."}
search_phrases:
  - sign-extend a byte or word
  - convert a signed 32-bit integer to 64 bits
  - widen a signed value to a larger register
  - read a signed byte from memory
  - convert a signed char to an int
related: [movzx, mov, cdqe, cqo]
---

## What it does

`movsx dst, src` copies a byte or word from a register or memory into the larger register `dst` and fills the higher bits with copies of the source's top (sign) bit, so a negative number stays negative. `movsxd` is the same idea for a 32-bit source and a 64-bit destination.

## When to use it

- Loading a signed byte or 16-bit value into a full register: `movsx eax, byte [rsi]`.
- Turning a signed 32-bit value into a 64-bit one before using it in 64-bit arithmetic or an address: `movsxd rax, ecx`.
- Preparing a value for signed comparison or division at a larger width.

## Gotchas

- **32-bit to 64-bit is `movsxd`** (opcode `63`, needs REX.W), not `movsx`. Without REX.W the `63` form is just a 32-bit copy, which zero-extends instead of sign-extending.
- **A plain 32-bit `mov` zero-extends,** so it is the wrong tool for signed 32-bit values that you need as 64-bit ones. This is a classic source of bugs when a negative `int` is used as an array index.
- **The destination must be wider than the source** (except for the degenerate 32-bit `movsxd`), and the source is a register or memory, not an immediate.
- **For unsigned values use `movzx`.**
- `cdqe` does the same job as `movsxd rax, eax` using only `rax`.
- **Byte registers.** With a REX prefix the byte source `ah`/`bh`/`ch`/`dh` is not available; the same bits select `spl`/`bpl`/`sil`/`dil`.
- It never changes the flags. A `lock` prefix is invalid (`#UD`).

## Example

```nasm
movsx  eax, byte [rsi]    ; eax = signed byte; bits 63:32 of rax are zero
movsx  rax, word [rsi]    ; rax = signed 16-bit value, sign-extended to 64 bits
movsxd rax, dword [rsi]   ; rax = signed 32-bit value, sign-extended to 64 bits
movsxd rax, ecx           ; sign-extend ecx into rax (what a negative int index needs)
```
