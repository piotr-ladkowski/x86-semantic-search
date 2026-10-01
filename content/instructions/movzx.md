---
slug: movzx
mnemonic: MOVZX
aliases: []
title: Move With Zero-Extend
summary: Copies a byte or word into a larger register and fills the upper bits with zeros.
category: data-transfer
status: draft
cpuid_feature: null
sdm_entries: ["MOVZX—Move With Zero-Extend"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "MOVZX r64, r/m8", opcode: "REX.W + 0F B6 /r"}
  - {syntax: "MOVZX r64, r/m16", opcode: "REX.W + 0F B7 /r"}
  - {syntax: "MOVZX r32, r/m8", opcode: "0F B6 /r", note: "Also zeroes bits 63:32 of the 64-bit register."}
  - {syntax: "MOVZX r32, r/m16", opcode: "0F B7 /r", note: "Also zeroes bits 63:32 of the 64-bit register."}
search_phrases:
  - zero-extend a byte or word
  - widen an unsigned value to a larger register
  - read an unsigned byte from memory
  - clear the upper bits when loading a small value
  - convert an unsigned char to an int
related: [movsx, mov, and, cdqe]
---

## What it does

`movzx dst, src` copies a byte or word from a register or memory into the larger register `dst`, and sets all the higher bits of `dst` to zero. The source is read-only; the destination must be wider than the source.

## When to use it

- Loading an unsigned byte or 16-bit value from memory into a full register: `movzx eax, byte [rsi]`.
- Widening a small unsigned value before arithmetic or before using it as an index.
- Cleaning stale upper bits left behind by 8- or 16-bit operations: `movzx eax, al`.

## Gotchas

- **There is no 32-bit to 64-bit `movzx`.** Zero-extending a doubleword to a quadword needs no special instruction: any 32-bit register write (`mov eax, ecx`) already clears bits 63:32.
- **The destination must be wider than the source,** and the source is a register or memory (not an immediate).
- **For signed values use `movsx`.** `movzx` on a negative byte gives a positive number (`0xFF` becomes 255).
- **Byte registers.** With a REX prefix the byte source `ah`/`bh`/`ch`/`dh` is not available; the same bits select `spl`/`bpl`/`sil`/`dil`.
- It never changes the flags. A `lock` prefix is invalid (`#UD`).

## Example

```nasm
movzx eax, byte [rsi]     ; eax = unsigned byte at [rsi]; bits 63:32 of rax are zero
movzx rax, word [rsi]     ; rax = unsigned 16-bit value at [rsi]
movzx ecx, al             ; ecx = al, upper bits cleared
mov   eax, ecx            ; 32 -> 64 bit zero-extension needs no movzx
```
