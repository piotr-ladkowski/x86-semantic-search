---
slug: pop
mnemonic: POP
aliases: []
title: Pop From the Stack
summary: Loads the value at the top of the stack into the destination, then increments RSP by 8.
category: data-transfer
status: draft
cpuid_feature: null
sdm_entries: ["POP—Pop a Value From the Stack"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "POP r64", opcode: "58+ rd", note: "A 16-bit form exists with the 66h prefix; a 32-bit pop cannot be encoded in 64-bit mode."}
  - {syntax: "POP r/m64", opcode: "8F /0"}
search_phrases:
  - restore a register from the stack
  - take a value off the stack
  - pop the top of the stack into a register
  - remove the last pushed value
related: [push, ret, leave, mov]
---

## What it does

`pop dst` reads the 8-byte value at `[rsp]`, stores it in `dst`, and then adds 8 to `rsp`. It undoes a `push`: the stack is last-in, first-out.

## When to use it

- Restoring registers saved with `push`, in the reverse order they were pushed.
- Moving a value from the stack into a register or memory location.
- Throwing a stack value away: pop into a scratch register (or add 8 to `rsp`).

## Gotchas

- **Operand size.** A 32-bit pop cannot be encoded in 64-bit mode; use a 64-bit operand (or the `66h` prefix for 16 bits). Popping into `DS`, `ES` or `SS` is not valid.
- **`pop rsp` loads `rsp` from the stack.** The stack pointer is incremented before the old top-of-stack value is written, so the final `rsp` is the popped value, not `rsp + 8`.
- **Memory destinations that use `rsp`.** For `pop [rsp + 8]` the destination address is computed after `rsp` has been incremented.
- **Faults.** A non-canonical stack address raises `#SS(0)`, a non-canonical memory destination `#GP(0)`, and an unmapped page a page fault (`#PF`). A `lock` prefix is invalid (`#UD`).
- It leaves all flags alone (`popf` is the instruction that pops into `rflags`).

## Example

```nasm
pop  rbx               ; rbx = [rsp]; rsp += 8
pop  qword [rdi]       ; store the top of the stack at [rdi]; rsp += 8

push rax
push rcx
pop  rax               ; rax = old rcx
pop  rcx               ; rcx = old rax  (swaps them through the stack)
```
