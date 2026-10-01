---
slug: rep
mnemonic: REP
aliases: [REPE, REPZ, REPNE, REPNZ]
title: Repeat String Operation (Prefix)
summary: Prefix that repeats one string instruction RCX times; REPE and REPNE also stop when ZF shows the comparison ended.
category: string
status: draft
cpuid_feature: null
sdm_entries:
  - "REP—Repeat String Operation (Prefix)"
  - "REPE/REPZ—Repeat String Operation While Zero (Prefix)"
  - "REPNE/REPNZ—Repeat String Operation While Not Zero (Prefix)"
extra_sources:
  - "Examples assembled with NASM 2.16.01 and run on Linux (x86-64): my_strlen('hello') = 5 and my_strlen('') = 0 with repne scasb; mem_equal gave 1, 0 and 1 for equal, different and empty comparisons."
flags:
  read: [ZF]
  note: "The prefixes do not change flags. REPE and REPNE read ZF (set by the CMPS or SCAS they repeat); REP itself ignores it."
forms:
  - {syntax: "REP MOVS / STOS / LODS", opcode: "F3 + string opcode", note: "e.g. rep movsb = F3 A4; rep stosq = F3 REX.W AB. (INS and OUTS also accept REP but are privileged.)"}
  - {syntax: "REPE CMPS / SCAS  (also REPZ)", opcode: "F3 + string opcode", note: "Repeat while the compared elements are equal (ZF = 1). The byte F3 is the same as for REP."}
  - {syntax: "REPNE CMPS / SCAS  (also REPNZ)", opcode: "F2 + string opcode", note: "Repeat while the compared elements differ (ZF = 0)."}
search_phrases:
  - repeat a string instruction
  - copy or fill memory with a single instruction
  - compare two buffers until they differ
  - find a byte in a buffer
  - implement strlen in assembly
  - find the end of a zero-terminated string
  - repeat a single instruction a given number of times
related: [movs, stos, lods, scas, cmps, loop, jcc]
---

## What it does

A repeat prefix placed before a string instruction (`movs`, `stos`, `lods`, `cmps`, `scas`) repeats that one instruction. The count register is `rcx` in 64-bit mode (`ecx` with a `67h` prefix; REX.W has no effect on it). Each repetition decrements `rcx`, and the repetition stops when it reaches zero:

| Prefix | Used with | Also stops when |
|---|---|---|
| `rep` | `movs`, `stos`, `lods` | (never; only the count) |
| `repe` / `repz` | `cmps`, `scas` | the comparison finds a difference (ZF = 0) |
| `repne` / `repnz` | `cmps`, `scas` | the comparison finds a match (ZF = 1) |

## When to use it

- Block copy and fill: `rep movsb`, `rep stosq`.
- Searching: `repne scasb` scans memory for the byte in `al`.
- Comparing buffers: `repe cmpsb` runs until the first mismatch.

## Gotchas

- **It repeats only one instruction.** The SDM is explicit that to repeat a block of instructions you use `loop` or another looping construct.
- **The count is tested before each repetition.** With `rcx = 0` the string instruction runs zero times. This is the opposite of `loop`, which decrements first and would run 2^64 times from zero. For `repe`/`repne` a zero count also means the flags are untouched, so a following `sete` would read stale data: guard with `jrcxz`, as `mem_equal` below does.
- **The prefix byte is shared.** `F3` means `rep` before `movs`/`stos`/`lods` and `repe` before `cmps`/`scas`; `F2` is `repne`. `rep cmpsb` and `repe cmpsb` therefore produce the same bytes.
- **After the instruction the registers have moved.** `rcx` holds the repetitions left and `rsi`/`rdi` point past the last element processed. After `repne scasb` finds a match, `rdi` is one past it.
- **The direction flag decides which way the pointers move,** and the System V ABI requires DF to be clear on entry and return.
- **Faults and interrupts.** Exceptions raised by the repeated instruction (non-canonical addresses, page faults) occur as usual; the prefix itself raises none.

## Example

```nasm
my_strlen:                      ; size_t my_strlen(const char *s)
        mov     rdx, rdi        ; remember where the string starts
        xor     eax, eax        ; scas compares with AL: look for the zero byte
        mov     rcx, -1         ; "no limit" on the count
        repne scasb             ; repeat while [rdi] != al, advancing rdi
        lea     rax, [rdi - 1]  ; rdi is one past the zero byte
        sub     rax, rdx        ; length = end - start
        ret

mem_equal:                      ; int mem_equal(const void *a, const void *b, size_t n)
        mov     rcx, rdx
        mov     eax, 1          ; an empty comparison counts as equal
        jrcxz   .done           ; n == 0: repe would run zero times and leave the flags untouched
        repe cmpsb              ; compare [rsi] with [rdi] until a byte differs or rcx reaches 0
        sete    al              ; ZF = 1 only if the last pair compared was equal
        movzx   eax, al
.done:  ret
```
