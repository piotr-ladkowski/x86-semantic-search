---
slug: nop
mnemonic: NOP
aliases: []
title: No Operation
summary: Does nothing except occupy one or more bytes in the instruction stream.
category: miscellaneous
status: draft
cpuid_feature: null
sdm_entries: ["NOP—No Operation"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "NOP", opcode: "90", note: "One byte. This is the encoding of XCHG (E)AX, (E)AX, treated as a NOP."}
  - {syntax: "NOP r/m32", opcode: "0F 1F /0", note: "Multi-byte NOP (also r/m16). Reads and writes nothing and issues no memory access, whatever the operand."}
search_phrases:
  - do nothing for one instruction
  - pad code to an alignment boundary
  - insert padding bytes between functions
  - a placeholder instruction
  - multi-byte no-op sequence
related: [xchg, pause, ud2, endbr64]
---

## What it does

`nop` performs no operation. It changes no register, flag or memory; the only state that moves is the instruction pointer. It exists to take up space in the instruction stream.

## When to use it

- Padding code so the next instruction or loop starts on an alignment boundary.
- Reserving room that a patcher or debugger can overwrite later.
- As a harmless placeholder while editing assembly.

## Gotchas

- **Single-byte `nop` is `xchg eax, eax`.** The SDM defines `90` as a NOP *regardless of any prefixes, including REX.W*, so it does not clear the upper half of `rax` the way other 32-bit instructions do.
- **Longer paddings use the multi-byte form,** `0F 1F /0`, for which the SDM gives recommended 2- to 9-byte sequences (table below). It issues no memory operation, so its "memory" operand is never accessed; the only exception listed is `#UD`.
- **A `lock` prefix is invalid** (`#UD`).

Recommended byte sequences (from the SDM) for the common lengths:

| Length | Bytes |
|---|---|
| 1 | `90` |
| 2 | `66 90` |
| 3 | `0F 1F 00` |
| 4 | `0F 1F 40 00` |
| 5 | `0F 1F 44 00 00` |
| 6 | `66 0F 1F 44 00 00` |
| 7 | `0F 1F 80 00 00 00 00` |
| 8 | `0F 1F 84 00 00 00 00 00` |
| 9 | `66 0F 1F 84 00 00 00 00 00` |

## Example

```nasm
nop                         ; 1 byte:  90
db 0x66, 0x90               ; 2 bytes: the recommended 2-byte NOP
db 0x0F, 0x1F, 0x00         ; 3 bytes: nop dword [rax]
db 0x0F, 0x1F, 0x40, 0x00   ; 4 bytes: nop dword [rax + 0]
```
