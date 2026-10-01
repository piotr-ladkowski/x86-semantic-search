---
slug: xor
mnemonic: XOR
aliases: []
title: Logical Exclusive OR
summary: Bitwise exclusive OR of destination and source, stored in the destination; xor reg, reg zeroes a register.
category: logical
status: draft
cpuid_feature: null
sdm_entries: ["XOR—Logical Exclusive OR"]
extra_sources:
  - "Zeroing-idiom behaviour: Intel 64 and IA-32 Architectures Optimization Reference Manual (not part of the SDM instruction reference)."
flags:
  modified: [OF, CF, SF, ZF, PF]
  undefined: [AF]
  note: "OF and CF are cleared; SF, ZF and PF are set from the result."
forms:
  - {syntax: "XOR r/m64, r64", opcode: "REX.W + 31 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W; the 8-bit opcode is 30 /r)."}
  - {syntax: "XOR r64, r/m64", opcode: "REX.W + 33 /r"}
  - {syntax: "XOR r/m64, imm8", opcode: "REX.W + 83 /6 ib", note: "imm8 is sign-extended to 64 bits."}
  - {syntax: "XOR r/m64, imm32", opcode: "REX.W + 81 /6 id", note: "imm32 is sign-extended to 64 bits."}
  - {syntax: "XOR RAX, imm32", opcode: "REX.W + 35 id"}
search_phrases:
  - zero a register
  - set a register to 0
  - clear a register
  - bitwise exclusive or
  - toggle or flip specific bits
  - find which bits differ between two values
related: [and, or, not, mov, popcnt]
---

## What it does

`xor dst, src` sets each bit of `dst` to 1 where the corresponding bits of `dst` and `src` differ, and to 0 where they are the same. XOR-ing a value with itself therefore always gives 0.

## When to use it

- **Zeroing a register:** `xor eax, eax`. This is what compilers emit instead of `mov eax, 0`.
- Flipping chosen bits (XOR with a mask), or comparing two values bit-by-bit: the set bits of `a ^ b` are the positions where they differ.
- Simple reversible mixing in checksums and ciphers (applying the same key twice restores the original).

## Gotchas

- **Zeroing idiom.** `xor eax, eax` is 2 bytes (`31 C0`); `mov eax, 0` is 5 (`B8 00 00 00 00`). Because 32-bit results are zero-extended, it clears all of `rax` too. `xor rax, rax` works but needs a REX.W prefix and is longer for no benefit. Modern CPUs also recognise the idiom and treat it specially.
- **It clobbers the flags.** XOR sets ZF/PF, clears CF/OF and leaves AF undefined. Do not place `xor reg, reg` between a `cmp` and the conditional jump, `setcc` or `cmovcc` that reads its flags; use `mov reg, 0` there, which does not touch flags.
- **Use `not` to invert every bit.** `xor rax, -1` gives the same value but also changes the flags.
- **At most one memory operand,** and `lock xor` needs a memory destination (otherwise `#UD`).

## Example

```nasm
xor  eax, eax                  ; rax = 0 (upper half cleared too); flags: ZF=1, CF=OF=0
xor  rax, rbx                  ; rax ^= rbx
xor  dword [rdi], 0x80000000   ; flip the sign bit of a 32-bit value in memory

; Hamming distance between rdi and rsi (needs POPCNT)
xor    rdi, rsi
popcnt rax, rdi
```
