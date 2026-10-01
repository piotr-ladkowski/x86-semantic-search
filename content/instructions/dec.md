---
slug: dec
mnemonic: DEC
aliases: []
title: Decrement by 1
summary: Subtracts 1 from the operand in place without changing the carry flag.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["DEC—Decrement by 1"]
extra_sources: []
flags:
  modified: [OF, SF, ZF, AF, PF]
  note: "CF is NOT affected; that is the difference from sub reg, 1."
forms:
  - {syntax: "DEC r/m64", opcode: "REX.W + FF /1", note: "The 32- and 16-bit forms are FF /1 and the 8-bit form is FE /1. The one-byte 48+ rd encodings of 32-bit mode do not exist in 64-bit mode."}
search_phrases:
  - decrease a counter by one
  - count a loop down to zero
  - decrement without changing the carry flag
  - subtract one in place
related: [inc, sub, neg, sbb, jcc]
---

## What it does

`dec dst` subtracts 1 from `dst` and stores the result back, setting OF, SF, ZF, AF and PF from the result while **leaving CF exactly as it was**.

## When to use it

- Counting down: `dec rcx` followed by `jnz` loops until `rcx` reaches zero, because ZF is set by the `dec` itself.
- Stepping an index backwards.
- Decrementing memory in place, atomically if you add `lock`: `lock dec dword [refcount]`.

## Gotchas

- **CF is preserved.** `sub rax, 1` updates CF; `dec rax` does not, which is what lets a loop counter live inside a multi-word subtraction (`sbb`) chain.
- **The short encodings are gone in 64-bit mode.** In 32-bit code `dec r32` was a single byte (`48`-`4F`); in 64-bit mode those bytes are REX prefixes, so only the `FF /1` (and `FE /1` for bytes) forms exist.
- **Wrap-around.** `dec` on 0 gives all ones (ZF clear, SF set), so a `dec`/`jnz` loop entered with `rcx = 0` runs 2^64 times. Test for zero before entering the loop.
- **32-bit operations zero the upper half.** `dec eax` clears bits 63:32 of `rax`.
- **`lock dec` needs a memory destination** (otherwise `#UD`).

## Example

```nasm
        mov  rcx, 10
.again: nop                 ; ... loop body, runs 10 times ...
        dec  rcx
        jnz  .again         ; ZF from dec; CF untouched

lock dec dword [refcount]   ; atomic decrement; ZF tells you whether it reached 0
```
