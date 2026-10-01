---
slug: xchg
mnemonic: XCHG
aliases: []
title: Exchange
summary: Swaps the contents of two operands; with a memory operand the swap is automatically atomic.
category: data-transfer
status: draft
cpuid_feature: null
sdm_entries: ["XCHG—Exchange Register/Memory With Register"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "XCHG r/m64, r64", opcode: "REX.W + 87 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W; the 8-bit opcode is 86 /r)."}
  - {syntax: "XCHG r64, r/m64", opcode: "REX.W + 87 /r"}
  - {syntax: "XCHG RAX, r64", opcode: "REX.W + 90+ rd", note: "Short form for exchanging with the accumulator."}
search_phrases:
  - swap two registers
  - exchange the values of two variables
  - atomically swap a register with memory
  - take a lock with an atomic exchange
  - swap the two bytes of a 16-bit register
related: [mov, cmpxchg, xadd, bswap, lock, nop]
---

## What it does

`xchg a, b` swaps the contents of its two operands in one instruction. The operands can be two registers, or a register and a memory location (never two memory locations). No temporary register is needed.

## When to use it

- Swapping two registers: `xchg rax, rbx`.
- An atomic swap with memory, the basis of simple spinlocks and flag handoffs: `xchg [lock_var], eax`.
- Swapping the two bytes of a 16-bit value (`xchg al, ah`), which the SDM notes can stand in for `bswap` at 16 bits.

## Gotchas

- **A memory operand makes it atomic.** The locking protocol is applied automatically, with or without a `lock` prefix. That gives you an atomic swap for free, but it also means an `xchg` with memory is a locked operation, not a plain load and store.
- **`xchg eax, eax` is the NOP.** The one-byte `90` encoding is defined as `nop` regardless of operand size or REX.W, so `xchg eax, eax` does **not** clear the upper half of `rax`. (Other 32-bit exchanges zero-extend both registers as usual.)
- **A `lock` prefix with two register operands is invalid** (`#UD`); `lock` only makes sense, and is redundant, with a memory operand.
- **At most one memory operand.**
- It does not change the flags.

## Example

```nasm
xchg rax, rbx              ; swap two registers
xchg [rdi], rax            ; atomic: rax <-> the qword at [rdi], no lock prefix needed
xchg al, ah                ; swap the two bytes of ax
```
