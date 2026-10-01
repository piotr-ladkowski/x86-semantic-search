---
slug: add
mnemonic: ADD
aliases: []
title: Add
summary: Adds the source to the destination, stores the sum in the destination, and sets the arithmetic flags.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["ADD—Add"]
extra_sources: []
flags:
  modified: [OF, SF, ZF, AF, CF, PF]
  note: "CF = unsigned carry out of the top bit; OF = signed overflow; ZF = result is zero; SF = sign bit of the result."
forms:
  - {syntax: "ADD r/m64, r64", opcode: "REX.W + 01 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W; the 8-bit opcode is 00 /r)."}
  - {syntax: "ADD r64, r/m64", opcode: "REX.W + 03 /r"}
  - {syntax: "ADD r/m64, imm8", opcode: "REX.W + 83 /0 ib", note: "imm8 is sign-extended to 64 bits."}
  - {syntax: "ADD r/m64, imm32", opcode: "REX.W + 81 /0 id", note: "imm32 is sign-extended to 64 bits. There is no imm64 form."}
  - {syntax: "ADD RAX, imm32", opcode: "REX.W + 05 id", note: "Short encoding for the accumulator."}
search_phrases:
  - add two numbers
  - add an immediate to a register
  - integer addition
  - sum two registers
  - add to a value in memory
  - detect carry or overflow when adding
  - what the carry flag means after an addition
related: [adc, sub, inc, lea, xadd, lock]
---

## What it does

`add dst, src` computes `dst = dst + src` and stores the result in `dst`. The same instruction serves signed and unsigned integers, because two's-complement addition produces identical bits for both. The flags report what happened: **CF** signals an unsigned overflow (carry out), **OF** a signed overflow, **ZF** a zero result and **SF** a negative one.

## When to use it

- Adding two integers, or a constant to a register: `add rax, 8`.
- Updating memory in place: `add dword [counter], 1`. Add the `lock` prefix to make it atomic.
- Multi-word arithmetic: `add` the low halves, then `adc` the high halves so the carry propagates.
- If you only need a sum in a *different* register, or must not disturb the flags, use `lea` instead.

## Gotchas

- **At most one memory operand.** The destination can be a register or memory; the source can be a register, memory (when the destination is a register) or an immediate.
- **Immediates are sign-extended.** The 64-bit forms take only a 32-bit immediate. To add a larger constant, `mov` it into a register first.
- **32-bit operations zero the upper half.** `add eax, ebx` clears bits 63:32 of `rax`; 8- and 16-bit adds leave the upper bits untouched.
- **`add reg, 1` is not `inc reg`.** `add` updates CF; `inc` leaves CF unchanged.
- **`lock add` needs a memory destination.** With a register destination the `lock` prefix raises `#UD`.
- **High-byte registers.** With any REX prefix, `ah`/`bh`/`ch`/`dh` cannot be encoded; the same bits select `spl`/`bpl`/`sil`/`dil`.

## Example

```nasm
add  rax, rbx                ; rax += rbx
add  rax, 16                 ; imm8 form, sign-extended
lock add qword [rdi], 1      ; atomic increment of a 64-bit counter

; 128-bit addition: rdx:rax += rcx:rbx
add  rax, rbx                ; low halves, sets CF on carry out
adc  rdx, rcx                ; high halves plus that carry
```
