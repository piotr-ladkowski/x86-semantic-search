---
slug: popcnt
mnemonic: POPCNT
aliases: []
title: Population Count
summary: Counts the bits set to 1 in the source and stores the count in the destination register.
category: bit-byte
status: draft
cpuid_feature: POPCNT
sdm_entries: ["POPCNT—Return the Count of Number of Bits Set to 1"]
extra_sources:
  - "Compiler flags: GCC and Clang documentation for __builtin_popcount and -mpopcnt."
flags:
  modified: [OF, SF, ZF, AF, CF, PF]
  note: "OF, SF, AF, CF and PF are cleared. ZF is set if the source is 0, otherwise cleared."
forms:
  - {syntax: "POPCNT r64, r/m64", opcode: "F3 REX.W 0F B8 /r"}
  - {syntax: "POPCNT r32, r/m32", opcode: "F3 0F B8 /r", note: "The upper 32 bits of the destination are zeroed. A 16-bit form also exists."}
search_phrases:
  - count the number of set bits
  - population count
  - hamming weight
  - count the ones in a bit pattern
  - number of 1 bits in a bitmask
  - hamming distance between two values
related: [lzcnt, tzcnt, bsf, bsr, xor]
---

## What it does

`popcnt dst, src` counts how many bits of `src` are 1 and writes that count (0 to 64) to the register `dst`. This is also called the *population count* or *Hamming weight*.

## When to use it

- Counting the elements in a bitset or bitmask.
- Hamming distance: `xor` two values, then `popcnt` the result.
- Testing whether a value is a power of two: exactly one bit is set.

## Gotchas

- **Not part of baseline x86-64.** It requires the POPCNT CPU feature (CPUID leaf 01H, ECX bit 23); on a CPU without it the instruction raises `#UD`. Check CPUID before use when you cannot assume a recent CPU.
- **The destination must be a register,** the source a register or memory. There is no immediate form and no 8-bit form.
- **Flags are simplified.** Only ZF carries information: it is set exactly when the source is zero, and all other status flags are cleared. So `popcnt rax, rbx` followed by `jz` tests "no bits set".
- **Compilers don't always emit it.** `__builtin_popcount` / `std::popcount` compile to the instruction only when the target allows it (for example `-mpopcnt` or `-march=x86-64-v2` or newer); otherwise you get a slower software fallback.
- A `lock` prefix raises `#UD`.

## Example

```nasm
popcnt rax, rdi        ; rax = number of 1 bits in rdi
popcnt ecx, [rsi]      ; ecx = number of 1 bits in the dword at [rsi]; rcx upper half zeroed

; is rdi a power of two? (exactly one bit set)
popcnt rax, rdi
cmp    rax, 1
je     .power_of_two
```
