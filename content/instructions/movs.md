---
slug: movs
mnemonic: MOVS
aliases: [MOVSB, MOVSW, MOVSD, MOVSQ]
title: Move String
summary: Copies one element from [RSI] to [RDI] and advances both pointers; with REP it is the classic block copy.
category: string
status: draft
cpuid_feature: null
sdm_entries: ["MOVS/MOVSB/MOVSW/MOVSD/MOVSQ—Move Data From String to String"]
extra_sources:
  - "Examples assembled with NASM 2.16.01 and run on Linux (x86-64): a forward and a backward copy of overlapping buffers gave 'ababab' and 'ababcd'; rep movsq copied three qwords."
flags:
  note: "No flags are affected. DF (the direction flag) is read, not changed."
forms:
  - {syntax: "MOVSB  (MOVS m8, m8)", opcode: "A4", note: "Copy 1 byte from [rsi] to [rdi]."}
  - {syntax: "MOVSD  (MOVS m32, m32)", opcode: "A5", note: "Copy 4 bytes. MOVSW (2 bytes) is the same opcode with the 66h prefix."}
  - {syntax: "MOVSQ  (MOVS m64, m64)", opcode: "REX.W + A5", note: "Copy 8 bytes."}
search_phrases:
  - copy a block of memory
  - copy bytes from one buffer to another
  - memory to memory copy in a single instruction
  - copy a string
  - implement memcpy in assembly
related: [rep, stos, cmps, lods, mov, loop]
---

## What it does

`movs` copies one element from the memory at `[rsi]` to the memory at `[rdi]`, then moves both pointers to the next element: up by the element size when the direction flag DF is 0, down when DF is 1. The suffix chooses the size: `movsb` 1 byte, `movsw` 2, `movsd` 4, `movsq` 8. It is the only common instruction that moves memory to memory.

On its own it copies a single element; with the [`rep` prefix](/instructions/rep) and a count in `rcx` it copies a whole block.

## When to use it

- Copying a buffer: set `rsi` (source), `rdi` (destination) and `rcx` (count), then `rep movsb`.
- Copying in larger units: `rep movsq` moves 8 bytes per repetition, with `rcx` counting qwords.
- Moving data backwards (overlapping buffers) by setting DF with `std`.

## Gotchas

- **The registers are fixed.** The source is always `rsi` and the destination always `rdi`; where an assembler accepts an explicit-operand spelling (`movs dst, src`), the operands only document the size. The SDM warns that this form can be misleading: the addresses always come from `rsi` and `rdi`.
- **`rcx` counts elements, not bytes.** `rep movsq` with `rcx = 8` copies 64 bytes.
- **Overlap needs the right direction.** A forward copy where the destination starts inside the source overwrites bytes before they are read: copying `"abcdef"` forward from offset 0 to offset 2, 4 bytes, gives `"ababab"`. Copy backwards instead, starting at the last element with DF = 1, and the result is `"ababcd"`. Restore DF with `cld` afterwards; the System V ABI requires it clear on function entry and return.
- **`movsd` is ambiguous.** With no operands it is this string instruction; with `xmm` operands it is the unrelated SSE2 floating-point move.
- **Faults.** A non-canonical address raises `#GP(0)` and an unmapped page a page fault. A `lock` prefix is invalid (`#UD`). Alignment checking (`#AC`) applies at privilege level 3 if enabled.
- It never changes the flags.

## Example

```nasm
copy_bytes:                     ; void copy_bytes(void *dst, const void *src, size_t n)
        mov     rcx, rdx        ; count
        rep movsb               ; repeat rcx times: [rdi] = [rsi], rsi += 1, rdi += 1
        ret

copy_qwords:                    ; void copy_qwords(void *dst, const void *src, size_t n_qwords)
        mov     rcx, rdx        ; the count is in qwords, not bytes
        rep movsq               ; repeat rcx times: [rdi] = [rsi] (8 bytes), rsi += 8, rdi += 8
        ret

copy_backward:                  ; void copy_backward(void *dst, const void *src, size_t n)
        lea     rsi, [rsi + rdx - 1]    ; start at the LAST byte of the source ...
        lea     rdi, [rdi + rdx - 1]    ; ... and of the destination
        mov     rcx, rdx
        std                     ; DF = 1: the pointers move down
        rep movsb
        cld                     ; put DF back to 0 (the System V ABI requires it clear on return)
        ret
```
