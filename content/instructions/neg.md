---
slug: neg
mnemonic: NEG
aliases: []
title: Two's Complement Negation
summary: Replaces the operand with its negative (0 minus the operand) and sets the flags.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["NEG—Two's Complement Negation"]
extra_sources: []
flags:
  modified: [OF, SF, ZF, AF, CF, PF]
  note: "CF is 0 if the operand was 0, otherwise 1. The rest are set from the result."
forms:
  - {syntax: "NEG r/m64", opcode: "REX.W + F7 /3", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
search_phrases:
  - negate a number
  - change the sign of an integer
  - turn a positive value into a negative one
  - two's complement of a register
  - compute zero minus a value
related: [not, sub, inc, dec, cmovcc]
---

## What it does

`neg dst` replaces `dst` with `0 - dst`, the two's-complement negative of the value. Positive becomes negative and the other way round; 0 stays 0.

## When to use it

- Flipping the sign of a signed integer: `neg rax`.
- Getting `0 - x` in one instruction when the operand is already in the register you want to change.
- Building an absolute value: negate a copy, then pick the positive one with a conditional move (`cmovcc`).

## Gotchas

- **CF means "was not zero".** After `neg`, CF is 0 only if the operand was 0, so `jnc`/`jae` after `neg` tells you the input was zero. It is not an overflow flag.
- **The most negative value has no positive counterpart.** Negating the smallest signed number (`0x8000000000000000` for a 64-bit register) gives the same value back, which is the signed-overflow case that OF reports.
- **Identity with NOT.** `neg x` equals `not x` followed by `inc x`.
- **32-bit operations zero the upper half.** `neg eax` clears bits 63:32 of `rax`.
- **`lock neg` needs a memory destination** (otherwise `#UD`).

## Example

```nasm
neg  rax                ; rax = -rax
neg  dword [rdi]        ; negate a 32-bit signed value in memory

; absolute value of rax
mov  rdx, rax
neg  rdx                ; rdx = -rax, SF = sign of the result
cmovs rdx, rax          ; if -rax is negative, rax was positive: use rax
mov  rax, rdx
```
