---
slug: lea
mnemonic: LEA
aliases: []
title: Load Effective Address
summary: Computes the address of a memory operand and stores it in a register without reading memory or changing flags.
category: miscellaneous
status: draft
cpuid_feature: null
sdm_entries: ["LEA—Load Effective Address"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "LEA r64, m", opcode: "REX.W + 8D /r"}
  - {syntax: "LEA r32, m", opcode: "8D /r", note: "The address is computed in 64 bits; the low 32 bits are stored and the upper half of the 64-bit register is zeroed."}
  - {syntax: "LEA r16, m", opcode: "8D /r", note: "Needs the 66h operand-size prefix; only the low 16 bits are stored."}
search_phrases:
  - calculate an address without loading from memory
  - get the address of a variable
  - multiply a register by 3, 5 or 9
  - add registers without changing flags
  - pointer arithmetic
  - load the address of a label relative to rip
related: [mov, add, shl, imul]
---

## What it does

`lea dst, [expr]` evaluates the address expression `base + index*scale + displacement` and stores the *result* in `dst`. Despite the bracket syntax, **no memory is accessed**: nothing is loaded or stored, so it cannot page-fault.

## When to use it

- Taking the address of data or code in position-independent 64-bit code: `lea rdi, [rip + message]`.
- Three-operand addition in one instruction: `lea rax, [rdi + rsi]` leaves both inputs intact.
- Cheap multiplication by 2, 3, 4, 5, 8 or 9 (`index*scale` with scale 1, 2, 4 or 8, plus the base): `lea eax, [rdi + rdi*4]` is `rdi * 5`.
- Doing arithmetic while **preserving the flags**, because LEA never modifies them.

## Gotchas

- **The source must be a memory operand.** `lea rax, rbx` is invalid (`#UD` at the machine level).
- **RIP-relative addressing** uses a signed 32-bit displacement relative to the *next* instruction, so the target must be within ±2 GiB.
- **Result size follows the destination register.** A 32-bit destination takes the low 32 bits of the computed address and zeroes the top half of the register; a 16-bit destination changes only the low 16 bits.
- **A `67h` address-size prefix** makes the address calculation 32-bit before it is zero-extended. This is rare outside deliberately truncating code.

## Example

```nasm
lea  rax, [rdi + rsi]          ; rax = rdi + rsi, flags untouched
lea  eax, [rdi + rdi*4]        ; eax = rdi * 5 (upper half of rax zeroed)
lea  rdx, [rip + message]      ; rdx = address of the label 'message'
lea  rcx, [rbx + rsi*8 + 16]   ; address of element rsi in an array of qwords at rbx+16
```
