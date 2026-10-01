---
slug: cmp
mnemonic: CMP
aliases: []
title: Compare
summary: Subtracts the second operand from the first and sets the flags, discarding the result.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["CMP—Compare Two Operands"]
extra_sources: []
flags:
  modified: [CF, OF, SF, ZF, AF, PF]
  note: "Set exactly as SUB would set them; no register or memory is written."
forms:
  - {syntax: "CMP r/m64, r64", opcode: "REX.W + 39 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W)."}
  - {syntax: "CMP r64, r/m64", opcode: "REX.W + 3B /r"}
  - {syntax: "CMP r/m64, imm8", opcode: "REX.W + 83 /7 ib", note: "imm8 is sign-extended to 64 bits."}
  - {syntax: "CMP r/m64, imm32", opcode: "REX.W + 81 /7 id", note: "imm32 is sign-extended to 64 bits."}
  - {syntax: "CMP RAX, imm32", opcode: "REX.W + 3D id", note: "Short encoding for the accumulator."}
search_phrases:
  - compare two values
  - set the flags for a conditional jump
  - check whether one number is greater than another
  - which of two numbers is bigger
  - is one register larger or smaller than another
  - compare against a constant
  - test whether two values are equal
related: [test, sub, jcc, setcc, cmovcc]
---

## What it does

`cmp a, b` computes `a - b`, sets the status flags from that result, and throws the result away: neither operand is changed. It exists to feed a conditional instruction (`jcc`, `setcc`, `cmovcc`), which reads the flags it left behind.

## When to use it

- Before a conditional jump, `setcc` or `cmovcc`: `cmp rax, rbx` then `jl`, `je` and so on.
- Comparing a register or memory value with a constant: `cmp dword [rdi], 10`.
- Checking equality (`je`/`jne`) or ordering. For a plain "is this zero?" test, `test reg, reg` is a byte shorter.

## Gotchas

- **Operand order.** `cmp a, b` computes `a - b`, so `cmp rax, rbx` followed by `jl` jumps when `rax < rbx` as signed numbers.
- **Signed versus unsigned is chosen by the instruction that reads the flags,** not by `cmp`: use `jb`/`ja` (and friends) for unsigned values and `jl`/`jg` for signed ones.
- **Immediates are sign-extended** to the size of the first operand: a 32-bit immediate with its top bit set means a negative number. To compare a 64-bit register with `4294967295`, load that constant into another register first.
- **At most one memory operand.**
- **A `lock` prefix is always invalid** (`#UD`), since `cmp` never writes.

## Example

```nasm
cmp  rax, rbx          ; flags from rax - rbx
jl   .less             ; taken if rax < rbx (signed)

cmp  dword [rdi], 10   ; compare a 32-bit value in memory with 10
je   .equal_ten

cmp  rcx, 0            ; works, but 'test rcx, rcx' is shorter
jne  .nonzero
```
