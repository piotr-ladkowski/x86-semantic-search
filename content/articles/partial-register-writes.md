---
slug: partial-register-writes
title: Why writing EAX clears the top half of RAX
summary: In 64-bit mode a 32-bit register write zero-extends into the full 64-bit register, but 8-bit and 16-bit writes do not.
tags: [registers, operand-size, 64-bit-mode]
status: draft
related_instructions: [mov, xor, movzx, movsx, cdqe, add]
sdm_refs: ["Vol. 1, section 3.4.1.1 General-Purpose Registers in 64-Bit Mode (PDF pages 78-79)", "Vol. 2, MOV—Move (PDF pages 1317-1320)"]
extra_sources: []
search_phrases:
  - why does mov eax clear the upper 32 bits of rax
  - zero extension of 32-bit register writes
  - upper bits of register after writing al or ax
  - partial register write behaviour in 64-bit mode
  - do I need to zero extend a 32-bit value to 64 bits
---

## The rule

When an instruction in 64-bit mode writes a general-purpose register, the **operand size** decides what happens to the bits it did not write:

| Operand size | What is written | Rest of the 64-bit register |
|---|---|---|
| 64-bit (`rax`) | all 64 bits | n/a |
| 32-bit (`eax`) | low 32 bits | **bits 63:32 are set to 0** (zero-extended) |
| 16-bit (`ax`) | low 16 bits | bits 63:16 are left unchanged |
| 8-bit (`al`, `ah`) | that byte | the other 56 bits are left unchanged |

The 32-bit case is the one that surprises people: `mov eax, ebx` is not "copy the low half and keep the high half", it replaces the whole of `rax`.

## What follows from it

- **Zeroing and small constants are cheaper in 32-bit form.** `xor eax, eax` clears all of `rax`, and `mov eax, 1` (5 bytes, `B8 01 00 00 00`) sets `rax` to 1 where the 64-bit `mov rax, 1` with a sign-extended imm32 takes 7 bytes. Compilers rely on this.
- **`mov eax, eax` zero-extends** the low 32 bits of `rax` in place, a common way to turn a 32-bit unsigned value into a 64-bit one.
- **Signed values need an explicit sign extension.** Use `movsxd rax, eax` (or `cdqe` for the accumulator) before using a signed 32-bit value in 64-bit arithmetic or an address.
- **8- and 16-bit writes keep stale upper bits.** After `mov al, 1` the rest of `rax` still holds whatever it held before, so zero-extend explicitly with `movzx eax, al` when you need a clean value, rather than relying on earlier contents. For address calculations the SDM says to sign-extend the register to the full 64 bits explicitly.

## Example

```nasm
mov  rax, -1          ; rax = 0xFFFFFFFFFFFFFFFF
mov  eax, 1           ; rax = 0x0000000000000001  (upper 32 bits cleared)

mov  rax, -1
mov  ax, 1            ; rax = 0xFFFFFFFFFFFF0001  (upper 48 bits kept)

mov  rax, -1
mov  eax, eax         ; rax = 0x00000000FFFFFFFF  (zero-extend the low half)
```
