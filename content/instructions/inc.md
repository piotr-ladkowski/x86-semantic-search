---
slug: inc
mnemonic: INC
aliases: []
title: Increment by 1
summary: Adds 1 to the operand in place without changing the carry flag.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["INC—Increment by 1"]
extra_sources: []
flags:
  modified: [OF, SF, ZF, AF, PF]
  note: "CF is NOT affected; that is the difference from add reg, 1."
forms:
  - {syntax: "INC r/m64", opcode: "REX.W + FF /0", note: "The 32-, 16- and 8-bit forms are FF /0 (32/16-bit) and FE /0 (8-bit). The one-byte 40+ rd encodings of 32-bit mode do not exist in 64-bit mode."}
search_phrases:
  - increase a counter by one
  - increment without changing the carry flag
  - bump a loop index
  - add one in place
related: [dec, add, neg, adc]
---

## What it does

`inc dst` adds 1 to `dst` and stores the result back, setting OF, SF, ZF, AF and PF from the result while **leaving CF exactly as it was**.

## When to use it

- Stepping a counter or index: `inc rcx`.
- Updating a loop counter inside a multi-word addition without disturbing the carry that `adc` is propagating.
- Incrementing memory in place, atomically if you add `lock`: `lock inc dword [counter]`.

## Gotchas

- **CF is preserved.** `add rax, 1` updates CF; `inc rax` does not. If a later `jc`/`jb` or `adc` depends on the carry of an earlier instruction, `inc` will not disturb it.
- **The short encodings are gone in 64-bit mode.** In 32-bit code, `inc r32` was a single byte (`40`-`47`); in 64-bit mode those bytes are REX prefixes, so only the `FF /0` (and `FE /0` for bytes) forms exist and are a byte longer.
- **32-bit operations zero the upper half.** `inc eax` clears bits 63:32 of `rax`.
- **`lock inc` needs a memory destination.** With a register destination the `lock` prefix raises `#UD`.

## Example

```nasm
inc  dword [rdi]            ; increment a 32-bit value in memory
lock inc qword [counter]    ; atomic increment of a 64-bit counter

stc                         ; CF = 1
inc  rcx                    ; rcx += 1 ... and CF is still 1
add  rcx, 1                 ; rcx += 1 ... but this one updates CF

        mov  rcx, -8        ; count up to zero
.again: nop                 ; ... loop body ...
        inc  rcx
        jnz  .again         ; ZF comes from the inc; CF is never touched
```
