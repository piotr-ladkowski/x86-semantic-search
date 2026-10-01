---
slug: rsi-rdi-string-registers
title: "RSI and RDI: the pointer registers behind the string instructions"
summary: How movs, stos, lods, scas and cmps use RSI and RDI as pointers that advance automatically, why rep needs RCX, and how Linux and Windows treat these registers differently.
tags: [registers, rsi, rdi, string-instructions]
status: draft
related_instructions: [movs, stos, lods, scas, cmps, rep, loop]
sdm_refs:
  - "Vol. 2, MOVS/MOVSB/MOVSW/MOVSD/MOVSQ (RSI and RDI hold the 64-bit addresses; incremented or decremented according to DF)"
  - "Vol. 2, STOS/STOSB/STOSW/STOSD/STOSQ; LODS/LODSB/LODSW/LODSD/LODSQ; SCAS/SCASB/SCASW/SCASD; CMPS; REP—Repeat String Operation (Prefix)"
extra_sources:
  - "System V AMD64 ABI draft 0.99.6, sections 3.2.1 (DF must be clear on function entry and return; %rdi and %rsi are scratch) and 3.2.3 (argument registers)."
  - "Microsoft 'x64 Calling Convention' documentation: RDI and RSI are nonvolatile."
  - "Example code assembled with NASM 2.16.01 and run on Linux (x86-64): fill_bytes via rep stosb and copy_bytes via rep movsb."
search_phrases:
  - what are rsi and rdi used for
  - which registers does movsb use
  - how does rep movsb know where to copy from and to
  - what does the direction flag do
  - why are rsi and rdi called source and destination index
---

## The idea

The string instructions work on memory through two implicit pointers: **`rsi` is the source** and **`rdi` is the destination**. After each element is processed, the instruction moves the pointers on by itself, so one instruction in a loop walks through whole buffers. These pointers are what `rsi` and `rdi` are *for*; for ordinary instructions they are just two more registers.

| Instruction | What it does with the pointers |
|---|---|
| `movs` (`movsb`, `movsw`, `movsd`, `movsq`) | Copy from `[rsi]` to `[rdi]`; advance both |
| `stos` | Store `al`/`ax`/`eax`/`rax` at `[rdi]`; advance `rdi` |
| `lods` | Load `al`/`ax`/`eax`/`rax` from `[rsi]`; advance `rsi` |
| `scas` | Compare `al`/`ax`/`eax`/`rax` with `[rdi]`; advance `rdi` |
| `cmps` | Compare `[rsi]` with `[rdi]`; advance both |

## How far, and which way

- Each instruction advances the pointers by the element size: 1, 2, 4 or 8 bytes.
- The direction depends on the **direction flag**. With DF = 0 (`cld`) the pointers move up in memory; with DF = 1 (`std`) they move down.
- In 64-bit mode the pointers are `rsi`/`rdi`. A `67h` prefix selects `esi`/`edi` instead, truncating the addresses.
- After the instruction the pointers have *moved*: `rdi` points just past the last byte stored, or, after a `scas` that found a match, just past the matching byte.

## Making them repeat

On their own they handle one element. Prefixing them with `rep` (or `repe`/`repne` for `cmps` and `scas`) repeats them while `rcx` counts down; see [RCX: the count register](/articles/rcx-count-register).

```nasm
copy_bytes:                     ; void copy_bytes(void *dst, const void *src, size_t n)
        mov     rcx, rdx        ; count
        rep movsb               ; repeat rcx times: [rdi] = [rsi], rsi += 1, rdi += 1
        ret
```

## Linux and Windows treat these registers differently

- **Linux (System V):** `rdi` and `rsi` are the 1st and 2nd argument registers, and they are *scratch*, so a function may clobber them freely. This lines up neatly with `memcpy(dst, src, n)`: the arguments arrive in `rdi`, `rsi`, `rdx`, exactly where `rep movsb` wants the first two. The ABI also requires **DF to be clear** on entry and return, so a function that sets it with `std` must restore it.
- **Windows (x64):** `rdi` and `rsi` are *nonvolatile*: a function that uses them must save and restore them. The arguments arrive in `rcx`, `rdx`, `r8`, `r9`, so a Windows copy routine has to `push rsi`, `push rdi`, move the arguments into place and pop them again.

This is why portable assembly that uses string instructions looks different on the two systems.

Instruction pages: [MOVS](/instructions/movs), [STOS](/instructions/stos), [REP](/instructions/rep).
