---
slug: push
mnemonic: PUSH
aliases: []
title: Push Onto the Stack
summary: Decrements RSP and stores the operand on the stack; in 64-bit mode the slot is 8 bytes.
category: data-transfer
status: draft
cpuid_feature: null
sdm_entries: ["PUSH—Push Word, Doubleword, or Quadword Onto the Stack"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "PUSH r64", opcode: "50+ rd", note: "A 16-bit form exists with the 66h prefix; a 32-bit push cannot be encoded in 64-bit mode."}
  - {syntax: "PUSH r/m64", opcode: "FF /6"}
  - {syntax: "PUSH imm32", opcode: "68 id", note: "Sign-extended to 64 bits; still pushes 8 bytes."}
  - {syntax: "PUSH imm8", opcode: "6A ib", note: "Sign-extended to 64 bits; still pushes 8 bytes."}
search_phrases:
  - save a register on the stack
  - put a value on the stack
  - preserve a register across a function call
  - pass an argument on the stack
  - push a constant onto the stack
related: [pop, call, ret, mov, enter, leave]
---

## What it does

`push src` subtracts 8 from `rsp` and then stores `src` at the new `[rsp]`, so the stack grows toward lower addresses. In 64-bit mode the default operand size is 64 bits, which is why each push uses an 8-byte slot.

## When to use it

- Saving a register you must preserve and restoring it later with `pop`, in the opposite order.
- Passing arguments or building a stack frame by hand.
- `call` pushes its own return address, so you do not push that yourself.

## Gotchas

- **Operand size.** A 32-bit push cannot be encoded in 64-bit mode. Push a 64-bit register, or use the `66h` prefix for a 16-bit push, which moves `rsp` by only 2 and leaves it misaligned.
- **Immediates are sign-extended.** `push imm32` pushes the 32-bit value sign-extended to 8 bytes, so you cannot push an arbitrary 64-bit constant directly; `mov` it into a register first.
- **`push rsp` pushes the value `rsp` had before the instruction.** If a memory operand's address uses `rsp`, that address is computed before `rsp` is decremented.
- **Faults.** A non-canonical stack address raises `#SS(0)`, a non-canonical memory operand `#GP(0)`, and running off the mapped stack a page fault (`#PF`). A `lock` prefix is invalid (`#UD`). Pushing `CS`, `SS`, `DS` or `ES` is not valid in 64-bit mode.
- It leaves all flags alone.

## Example

```nasm
push rbx               ; rsp -= 8, then [rsp] = rbx
push 42                ; imm8 sign-extended: still an 8-byte slot
push qword [rdi]       ; push the qword stored at [rdi]
push rsp               ; pushes the value rsp had before this instruction
```
