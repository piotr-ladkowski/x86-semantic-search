---
slug: mov
mnemonic: MOV
aliases: []
title: Move
summary: Copies the source operand to the destination without changing any flags.
category: data-transfer
status: draft
cpuid_feature: null
sdm_entries: ["MOV—Move"]
extra_sources: []
flags:
  note: "No flags are affected."
forms:
  - {syntax: "MOV r/m64, r64", opcode: "REX.W + 89 /r", note: "The 8-, 16- and 32-bit forms have the same shape (drop REX.W; the 8-bit opcode is 88 /r)."}
  - {syntax: "MOV r64, r/m64", opcode: "REX.W + 8B /r"}
  - {syntax: "MOV r64, imm64", opcode: "REX.W + B8+ rd io", note: "Loads a full 64-bit constant (assemblers often call this movabs). Every other MOV form takes at most a 32-bit immediate."}
  - {syntax: "MOV r/m64, imm32", opcode: "REX.W + C7 /0 id", note: "imm32 is sign-extended to 64 bits."}
  - {syntax: "MOV r32, imm32", opcode: "B8+ rd id", note: "The upper 32 bits of the 64-bit register are zeroed."}
search_phrases:
  - copy a value from one register to another
  - load a constant into a register
  - put a number into a register
  - read a value from memory
  - write a register to memory
  - load a full 64-bit constant
related: [movzx, movsx, lea, xchg, push, pop, xor]
---

## What it does

`mov dst, src` copies `src` into `dst` and leaves `src` unchanged. Both operands must be the same size (8, 16, 32 or 64 bits). The source can be a register, a memory location or an immediate value; the destination is a register or a memory location. It never touches the flags.

## When to use it

- Copying between registers: `mov rax, rbx`.
- Loading a constant into a register: `mov eax, 42`.
- Reading or writing memory: `mov rax, [rdi]` and `mov [rdi], rax`.
- When you only need to move a value. To compute an address or a sum use `lea` or `add`; to swap two values use `xchg`; to widen a smaller value use `movzx` or `movsx`.

## Gotchas

- **No memory-to-memory move.** At most one operand can be in memory, so go through a register.
- **32-bit moves zero the upper half.** `mov eax, ebx` clears bits 63:32 of `rax`. 8- and 16-bit moves leave the other bits alone (see the article on partial register writes).
- **Immediates are small unless you ask for 64 bits.** Only `mov r64, imm64` carries a full 64-bit constant. `mov r/m64, imm32` sign-extends, so `mov qword [rdi], 0xFFFFFFFF` stores `0xFFFFFFFFFFFFFFFF`, not `0x00000000FFFFFFFF`; to store the latter, load it with `mov eax, 0xFFFFFFFF` first.
- **It does not change flags,** which is why `mov reg, 0` is the safe way to zero a register between a `cmp` and the conditional jump that reads its flags (`xor reg, reg` would clobber them).
- **Faults and limits.** A non-canonical memory address raises `#GP(0)`. `mov` cannot load `CS` (`#UD`), and a `lock` prefix is invalid (`#UD`); use `xchg` for an atomic exchange.
- With any REX prefix, `ah`/`bh`/`ch`/`dh` cannot be encoded; the same bits select `spl`/`bpl`/`sil`/`dil`.

## Example

```nasm
mov  rax, rbx                  ; copy a register
mov  eax, 1                    ; rax = 1 (upper half cleared)
mov  rax, 0x1122334455667788   ; full 64-bit constant
mov  qword [rdi], 0            ; store zero (imm32 sign-extended to 64 bits)
mov  rax, [rsi + rcx*8]        ; load element rcx of a qword array
mov  [rdi], rax                ; store it back
```
