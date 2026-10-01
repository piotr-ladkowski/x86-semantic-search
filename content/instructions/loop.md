---
slug: loop
mnemonic: LOOP
aliases: [LOOPE, LOOPZ, LOOPNE, LOOPNZ]
title: Loop According to the Counter Register
summary: Decrements RCX and jumps to a nearby label while it is not zero; LOOPE and LOOPNE also test ZF.
category: control-transfer
status: draft
cpuid_feature: null
sdm_entries: ["LOOP/LOOPcc—Loop According to ECX Counter"]
extra_sources:
  - "Wikibooks, 'x86 Assembly/Print Version', section 'Loop Instructions' (CC BY-SA): used as a map of the topic; its ECX-only description was corrected against the SDM for 64-bit mode."
flags:
  read: [ZF]
  note: "No flags are modified. LOOPE/LOOPZ read ZF (continue while ZF = 1); LOOPNE/LOOPNZ read ZF (continue while ZF = 0). LOOP itself ignores the flags."
forms:
  - {syntax: "LOOP rel8", opcode: "E2 cb", note: "rcx -= 1; jump if rcx != 0. The target must lie within -128..+127 bytes of the next instruction."}
  - {syntax: "LOOPE rel8", opcode: "E1 cb", note: "Also LOOPZ. rcx -= 1; jump if rcx != 0 and ZF = 1."}
  - {syntax: "LOOPNE rel8", opcode: "E0 cb", note: "Also LOOPNZ. rcx -= 1; jump if rcx != 0 and ZF = 0."}
search_phrases:
  - repeat a block of code a fixed number of times
  - loop until the counter register reaches zero
  - count down and branch in one instruction
  - keep looping while a comparison stays equal
  - stop a scan loop when a byte matches
related: [jcc, dec, rep, cmp, jmp]
---

## What it does

`loop label` subtracts 1 from the counter register `rcx` and then, if the result is not zero, jumps to `label`. When `rcx` reaches zero execution falls through to the next instruction. It does the counting and the branching in one instruction and changes no flags.

`loope`/`loopz` and `loopne`/`loopnz` add a second condition: they keep looping only while `rcx` is non-zero **and** ZF is 1 (`loope`) or 0 (`loopne`). They only read ZF; something else inside the loop body must set it.

## When to use it

- Running a block a known number of times: put the count in `rcx`, end the body with `loop`.
- Searching or comparing with an early exit: `loopne` stops when the count runs out or a comparison sets ZF.
- If you also need the flags from the decrement, a `dec rcx` / `jnz` pair does the same job and updates them.

## Gotchas

- **The counter is `rcx` in 64-bit mode** (`ecx` only if you add a `67h` address-size prefix). `loop` ignores REX.W, so there is no separate 64-bit form to choose.
- **It decrements first, then tests.** Entering the loop with `rcx = 0` wraps it to all ones, so the body runs 2^64 times. Check for zero first (see `jrcxz` in `jcc`).
- **Short range only.** The target is an 8-bit signed offset: -128 to +127 bytes from the next instruction. A loop body longer than that cannot use `loop`; use `dec rcx` and `jnz`.
- **Mind the flags inside the body.** `loope`/`loopne` use the ZF left by the last flag-setting instruction in the body. Use `lea` instead of `add`/`inc` for pointer stepping there, because `add` and `inc` overwrite ZF.
- **A non-canonical target raises `#GP(0)`,** and a `lock` prefix is invalid (`#UD`).

## Example

```nasm
        mov  ecx, 10          ; writes rcx (upper half zeroed): the body runs 10 times
.again: ; ... loop body ...
        loop .again           ; rcx -= 1, jump back while rcx != 0

; find the first zero byte in a 64-byte buffer
        lea  rsi, [buf]
        mov  ecx, 64
.scan:  cmp  byte [rsi], 0    ; ZF = 1 if this byte is zero
        lea  rsi, [rsi + 1]   ; step the pointer without touching ZF
        loopne .scan          ; continue while rcx != 0 and the byte was non-zero
```
