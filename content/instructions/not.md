---
slug: not
mnemonic: NOT
aliases: []
title: One's Complement Negation
summary: Inverts every bit of the operand in place; unlike most logic instructions it changes no flags.
category: logical
status: draft
cpuid_feature: null
sdm_entries: ["NOT—One's Complement Negation"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "NOT r/m64", opcode: "REX.W + F7 /2", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
search_phrases:
  - invert all the bits
  - flip every bit of a register
  - bitwise complement
  - one's complement
related: [neg, xor, and, or]
---

## What it does

`not dst` replaces each 1 bit of `dst` with 0 and each 0 with 1. It takes a single operand, a register or a memory location, and changes it in place.

## When to use it

- Building the inverse of a mask, for example to clear bits with `and`.
- Computing a bitwise complement without disturbing the flags.
- Together with `inc`, as negation: `not rax` then `inc rax` gives `-rax` (use `neg` instead).

## Gotchas

- **It sets no flags.** `xor rax, -1` produces the same value but also changes SF/ZF/PF/OF/CF, so `not` is the safe choice between a `cmp` and the instruction that reads its flags.
- **32-bit operations zero the upper half.** `not eax` writes the inverted low 32 bits and clears bits 63:32, which differs from `not rax`.
- **One operand only,** no immediate form; it works on a register or a memory location.
- **`lock not` needs a memory destination** (otherwise `#UD`).

## Example

```nasm
not  rax                ; rax = ~rax
not  dword [rdi]        ; invert a 32-bit value in memory
not  rbx                ; rbx = the mask, inverted
and  rax, rbx           ; clears in rax every bit that was set in the original mask
```
