---
slug: and
mnemonic: AND
aliases: []
title: Logical AND
summary: Bitwise AND of destination and source, stored in the destination; used to mask or clear bits.
category: logical
status: draft
cpuid_feature: null
sdm_entries: ["AND—Logical AND"]
extra_sources: []
flags:
  modified: [OF, CF, SF, ZF, PF]
  undefined: [AF]
  note: "OF and CF are cleared; SF, ZF and PF are set from the result."
forms:
  - {syntax: "AND r/m64, r64", opcode: "REX.W + 21 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "AND r64, r/m64", opcode: "REX.W + 23 /r"}
  - {syntax: "AND r/m64, imm8", opcode: "REX.W + 83 /4 ib", note: "imm8 is sign-extended to 64 bits."}
  - {syntax: "AND r/m64, imm32", opcode: "REX.W + 81 /4 id", note: "imm32 is sign-extended to 64 bits."}
  - {syntax: "AND RAX, imm32", opcode: "REX.W + 25 id"}
search_phrases:
  - mask out some bits of a value
  - clear specific bits
  - keep only the low bits of a number
  - bitwise and
  - align a pointer to a power-of-two boundary
  - round an address down to a multiple of 16
related: [or, xor, not, test, andn, bt]
---

## What it does

`and dst, src` sets each bit of `dst` to 1 only where both `dst` and `src` have a 1, and to 0 everywhere else, and stores the result in `dst`. ANDing with a mask keeps the bits where the mask has 1s and clears the rest.

## When to use it

- Keeping only some bits: `and eax, 0xFF` leaves just the low byte.
- Clearing specific bits: AND with the inverted mask.
- Rounding down to a power-of-two boundary: `and rsp, -16` clears the low 4 bits.
- If you only want the flags and not the result, use `test`, which is an `and` that discards its result.

## Gotchas

- **Immediates are sign-extended.** A 32-bit immediate with its top bit set becomes a mask with all upper bits set, which clears nothing there. So a 64-bit `and` cannot mask with `0xFFFFFFFF` using an immediate; use a 32-bit operation instead (`mov eax, eax`), which zeroes the upper half.
- **32-bit operations zero the upper half.** `and eax, ebx` clears bits 63:32 of `rax`.
- **Flags.** OF and CF are cleared, SF/ZF/PF are set from the result, and AF is undefined.
- **At most one memory operand,** and `lock and` needs a memory destination (otherwise `#UD`).

## Example

```nasm
and  eax, 0xFF              ; keep the low byte (rax upper bits become 0)
and  rax, -33               ; clear bit 5 only (-33 is ~0x20, sign-extended)
and  rsp, -16               ; round rsp down to a multiple of 16
lock and qword [rdi], -2    ; atomically clear bit 0 of a qword in memory
```
