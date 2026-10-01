---
slug: stos
mnemonic: STOS
aliases: [STOSB, STOSW, STOSD, STOSQ]
title: Store String
summary: Stores AL, AX, EAX or RAX at [RDI] and advances RDI; with REP it fills a block of memory.
category: string
status: draft
cpuid_feature: null
sdm_entries: ["STOS/STOSB/STOSW/STOSD/STOSQ—Store String"]
extra_sources:
  - "Example assembled with NASM 2.16.01 and run on Linux (x86-64): fill_bytes(buf, 'a', 4) filled four bytes."
flags:
  note: "No flags are affected. DF (the direction flag) is read, not changed."
forms:
  - {syntax: "STOSB  (STOS m8)", opcode: "AA", note: "Store AL at [rdi]."}
  - {syntax: "STOSD  (STOS m32)", opcode: "AB", note: "Store EAX at [rdi]. STOSW (store AX) is the same opcode with the 66h prefix."}
  - {syntax: "STOSQ  (STOS m64)", opcode: "REX.W + AB", note: "Store RAX at [rdi]."}
search_phrases:
  - fill a block of memory with a value
  - clear a buffer to zero
  - implement memset in assembly
  - initialise an array with one value
  - store the accumulator and advance the pointer
related: [rep, movs, lods, scas, mov, xor]
---

## What it does

`stos` stores the accumulator (`al`, `ax`, `eax` or `rax`, depending on the suffix) at the memory addressed by `rdi`, then moves `rdi` to the next element: up when the direction flag DF is 0, down when it is 1. With the [`rep` prefix](/instructions/rep) and a count in `rcx` it fills a whole block with one value.

## When to use it

- Filling or clearing memory: `xor eax, eax` then `rep stosq` zeroes a block.
- Filling with a repeating byte pattern: put the byte in `al` and use `rep stosb`.
- Writing a sequence of values one at a time while walking a pointer.

## Gotchas

- **The registers are fixed.** The value comes from the accumulator, the address from `rdi`, and the repeat count (with `rep`) from `rcx`.
- **`rcx` counts elements, not bytes.** `rep stosq` with `rcx = 64` writes 512 bytes.
- **`stosq` stores all of `rax`,** so to fill with a byte value using the 8-byte form you must first replicate the byte across `rax`.
- **Direction.** With DF = 1 the pointer walks downward; the System V ABI guarantees DF is clear on function entry and return.
- **Faults.** A non-canonical address raises `#GP(0)` and an unmapped page a page fault. A `lock` prefix is invalid (`#UD`).
- It never changes the flags.

## Example

```nasm
fill_bytes:                     ; void fill_bytes(void *dst, int byte, size_t n)
        mov     rcx, rdx        ; rep uses rcx as its repeat count
        mov     eax, esi        ; stosb stores AL
        rep stosb               ; repeat rcx times: [rdi] = al, rdi += 1
        ret

xor     eax, eax                ; value to store: 0
mov     ecx, 64                 ; 64 qwords = 512 bytes
rep stosq                       ; zero 512 bytes starting at [rdi]
```
