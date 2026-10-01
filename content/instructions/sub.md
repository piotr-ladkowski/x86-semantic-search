---
slug: sub
mnemonic: SUB
aliases: []
title: Subtract
summary: Subtracts the source from the destination, stores the difference in the destination, and sets the arithmetic flags.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["SUB—Subtract"]
extra_sources: []
flags:
  modified: [OF, SF, ZF, AF, CF, PF]
  note: "CF is set when an unsigned borrow occurs (the source is larger than the destination); OF is signed overflow; ZF means the result is zero."
forms:
  - {syntax: "SUB r/m64, r64", opcode: "REX.W + 29 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "SUB r64, r/m64", opcode: "REX.W + 2B /r"}
  - {syntax: "SUB r/m64, imm8", opcode: "REX.W + 83 /5 ib", note: "imm8 is sign-extended to 64 bits."}
  - {syntax: "SUB r/m64, imm32", opcode: "REX.W + 81 /5 id", note: "imm32 is sign-extended to 64 bits. There is no imm64 form."}
  - {syntax: "SUB RAX, imm32", opcode: "REX.W + 2D id", note: "Short encoding for the accumulator."}
search_phrases:
  - subtract one number from another
  - integer subtraction
  - take a value away from a register
  - compute the difference of two values
  - detect borrow or overflow when subtracting
related: [sbb, cmp, add, dec, neg]
---

## What it does

`sub dst, src` computes `dst = dst - src` and stores the result in `dst`. Signed and unsigned subtraction produce the same bits, and the flags describe both: **CF** reports an unsigned borrow, **OF** a signed overflow, **ZF** a zero result and **SF** a negative one.

## When to use it

- Subtracting two integers, or a constant from a register: `sub rax, 8`.
- Updating memory in place: `sub dword [counter], 1` (add `lock` to make it atomic).
- Multi-word arithmetic: `sub` the low halves, then `sbb` the high halves so the borrow propagates.
- If you only want the flags and not the result, use `cmp`, which is a `sub` that throws the result away.

## Gotchas

- **Operand order matters.** `sub rax, rbx` is `rax - rbx`, not `rbx - rax`.
- **At most one memory operand.** The destination can be a register or memory; the source a register, memory (with a register destination) or an immediate.
- **Immediates are sign-extended.** The 64-bit forms take only a 32-bit immediate; to subtract a larger constant, `mov` it into a register first.
- **32-bit operations zero the upper half.** `sub eax, ebx` clears bits 63:32 of `rax`; 8- and 16-bit versions leave the upper bits alone.
- **`lock sub` needs a memory destination.** With a register destination the `lock` prefix raises `#UD`.

## Example

```nasm
sub  rax, rbx                ; rax -= rbx
sub  rsp, 32                 ; reserve 32 bytes of stack
sub  qword [rdi], 1          ; decrement a 64-bit value in memory (flags updated, CF included)

; 128-bit subtraction: rdx:rax -= rcx:rbx
sub  rax, rbx                ; low halves, CF = borrow
sbb  rdx, rcx                ; high halves minus that borrow
```
