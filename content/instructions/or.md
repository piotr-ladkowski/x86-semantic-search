---
slug: or
mnemonic: OR
aliases: []
title: Logical Inclusive OR
summary: Bitwise OR of destination and source, stored in the destination; used to set bits.
category: logical
status: draft
cpuid_feature: null
sdm_entries: ["OR—Logical Inclusive OR"]
extra_sources: []
flags:
  modified: [OF, CF, SF, ZF, PF]
  undefined: [AF]
  note: "OF and CF are cleared; SF, ZF and PF are set from the result."
forms:
  - {syntax: "OR r/m64, r64", opcode: "REX.W + 09 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "OR r64, r/m64", opcode: "REX.W + 0B /r"}
  - {syntax: "OR r/m64, imm8", opcode: "REX.W + 83 /1 ib", note: "imm8 is sign-extended to 64 bits."}
  - {syntax: "OR r/m64, imm32", opcode: "REX.W + 81 /1 id", note: "imm32 is sign-extended to 64 bits."}
  - {syntax: "OR RAX, imm32", opcode: "REX.W + 0D id"}
search_phrases:
  - turn bits on with a mask
  - set specific bits
  - turn on a single bit
  - set bit number n to 1
  - combine two bit masks
  - bitwise or
  - add a flag to a set of option bits
related: [and, xor, not, test, bts]
---

## What it does

`or dst, src` sets each bit of `dst` to 1 where either `dst` or `src` has a 1, and stores the result in `dst`. ORing with a mask turns on the bits where the mask has 1s and leaves the rest alone.

## When to use it

- Turning bits on: `or eax, 0x20` sets bit 5.
- Combining bit fields or flag constants into one value.
- Setting a bit in memory atomically: `lock or dword [rdi], 1`.

## Gotchas

- **Immediates are sign-extended.** A 32-bit immediate with its top bit set also sets every bit above it in a 64-bit `or`. To set just bit 31 of a 64-bit register, use `bts rax, 31`.
- **Setting every bit.** `or rax, -1` (imm8 `-1`, sign-extended) sets all 64 bits, without needing a 64-bit constant.
- **32-bit operations zero the upper half.** `or eax, ebx` clears bits 63:32 of `rax`.
- **Flags.** OF and CF are cleared, SF/ZF/PF are set from the result, and AF is undefined.
- **At most one memory operand,** and `lock or` needs a memory destination (otherwise `#UD`).

## Example

```nasm
or   eax, 0x20              ; set bit 5 (rax upper bits become 0)
or   rax, rbx               ; rax |= rbx
or   rax, -1                ; rax = 0xFFFFFFFFFFFFFFFF
lock or dword [rdi], 1      ; atomically set bit 0 of a dword in memory
```
