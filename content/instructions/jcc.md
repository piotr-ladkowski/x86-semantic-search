---
slug: jcc
mnemonic: JCC
aliases: [JA, JAE, JB, JBE, JC, JE, JG, JGE, JL, JLE, JNA, JNAE, JNB, JNBE, JNC, JNE, JNG, JNGE, JNL, JNLE, JNO, JNP, JNS, JNZ, JO, JP, JPE, JPO, JS, JZ, JRCXZ, JECXZ]
title: Jump if Condition Is Met
summary: Jumps to a nearby label if the status flags satisfy a condition, otherwise falls through; JRCXZ tests RCX instead.
category: control-transfer
status: draft
cpuid_feature: null
sdm_entries: ["Jcc—Jump if Condition Is Met"]
extra_sources:
  - "Wikibooks, 'x86 Assembly/Print Version', section 'Jump if counter register is zero' (CC BY-SA): used as a map of the topic."
flags:
  read: [CF, ZF, SF, OF, PF]
  note: "No flags are modified. Which flags are read depends on the condition; JRCXZ reads no flags."
forms:
  - {syntax: "Jcc rel8", opcode: "70+cc cb  (70-7F)", note: "Short form: target within -128..+127 bytes of the next instruction."}
  - {syntax: "Jcc rel32", opcode: "0F 80+cc cd  (0F 80-0F 8F)", note: "Near form: signed 32-bit offset, reaching +-2 GiB."}
  - {syntax: "JRCXZ rel8", opcode: "E3 cb", note: "Jump if RCX = 0. Short form only. JECXZ (tests ECX) is the same opcode with a 67h prefix."}
search_phrases:
  - jump to a label only if a condition holds
  - branch if the previous comparison was equal
  - jump if a value is less than another signed number
  - jump if above or below for unsigned numbers
  - jump when the result was zero
  - skip code depending on a flag
  - jump if the counter register is zero
related: [cmp, test, loop, jmp, setcc, cmovcc]
---

## What it does

`jcc label` is a family of instructions that jump to `label` when the status flags are in a particular state, and otherwise do nothing so execution continues with the next instruction. The letters after `j` name the condition. They read the flags left by an earlier instruction (usually `cmp` or `test`) and never change them.

The SDM uses **greater/less for signed** numbers and **above/below for unsigned** ones. Several names are synonyms for one opcode (`je` = `jz`, `jb` = `jc` = `jnae`).

| Jump if... | Mnemonics | Flags tested | After `cmp a, b` |
|---|---|---|---|
| equal / zero | JE, JZ | ZF = 1 | a = b |
| not equal / not zero | JNE, JNZ | ZF = 0 | a != b |
| above | JA, JNBE | CF = 0 and ZF = 0 | a > b, unsigned |
| above or equal | JAE, JNB, JNC | CF = 0 | a >= b, unsigned |
| below | JB, JNAE, JC | CF = 1 | a < b, unsigned |
| below or equal | JBE, JNA | CF = 1 or ZF = 1 | a <= b, unsigned |
| greater | JG, JNLE | ZF = 0 and SF = OF | a > b, signed |
| greater or equal | JGE, JNL | SF = OF | a >= b, signed |
| less | JL, JNGE | SF != OF | a < b, signed |
| less or equal | JLE, JNG | ZF = 1 or SF != OF | a <= b, signed |
| overflow / no overflow | JO / JNO | OF = 1 / OF = 0 | |
| sign / no sign | JS / JNS | SF = 1 / SF = 0 | result negative / non-negative |
| parity even / odd | JP, JPE / JNP, JPO | PF = 1 / PF = 0 | |
| RCX is zero | JRCXZ | RCX = 0 (no flags) | |

## When to use it

- Right after `cmp` or `test` to choose between two paths, or to build `if`, `while` and `for` constructs.
- To leave a loop early, or to guard a `loop`/`rep` against a zero count (`jrcxz`).
- Choose the signed (`jl`, `jg`) or unsigned (`jb`, `ja`) family according to how you interpret the numbers; the same `cmp` serves both.

## Gotchas

- **Signed versus unsigned is your choice, not the CPU's.** After `cmp rax, rbx`, `jl` and `jb` test different flags and give different answers when the top bit is set. Pick the family that matches the type of your data.
- **Range of the short form.** `Jcc rel8` reaches only -128 to +127 bytes from the next instruction. Farther targets need the near form (`0F 8x cd`), which assemblers can choose for you.
- **Keep the flags intact between the test and the jump.** Any instruction that writes flags in between changes the outcome; this is why `mov reg, 0` rather than `xor reg, reg` belongs there.
- **`jrcxz` is special.** It tests `rcx` itself (not the flags), has only the short form, and uses `ecx` if you add a `67h` prefix. It is the safe guard in front of a `loop` or `rep`.
- **Near jumps only.** A `jcc` cannot jump to another code segment, and a non-canonical target raises `#GP(0)`. A `lock` prefix is invalid (`#UD`).
- It never modifies the flags.

## Example

```nasm
        cmp   rax, rbx
        jl    .signed_less      ; taken if rax < rbx as signed numbers
        jb    .unsigned_below   ; taken if rax < rbx as unsigned numbers

        test  rcx, rcx
        jz    .rcx_is_zero      ; ZF = 1 if rcx == 0

        jrcxz .skip_loop        ; jump if rcx == 0, without looking at the flags
.again: ; ... loop body ...
        loop  .again
.skip_loop:
```
