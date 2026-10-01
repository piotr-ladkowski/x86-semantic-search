---
slug: imul
mnemonic: IMUL
aliases: []
title: Signed Multiply
summary: Signed multiply with one-, two- or three-operand forms; the multi-operand forms keep only the low half of the product.
category: binary-arithmetic
status: draft
cpuid_feature: null
sdm_entries: ["IMUL—Signed Multiply"]
extra_sources: []
flags:
  modified: [OF, CF]
  undefined: [SF, ZF, AF, PF]
  note: "Two- and three-operand forms: CF and OF are set when the result had to be truncated to fit the destination. One-operand form: set when the product does not fit in the lower half (RAX)."
forms:
  - {syntax: "IMUL r64, r/m64", opcode: "REX.W + 0F AF /r", note: "dst = dst * src, truncated to 64 bits. 16- and 32-bit versions exist; there is no 8-bit version of this form."}
  - {syntax: "IMUL r64, r/m64, imm8", opcode: "REX.W + 6B /r ib", note: "dst = src * imm8 (sign-extended). Does not modify the source."}
  - {syntax: "IMUL r64, r/m64, imm32", opcode: "REX.W + 69 /r id", note: "dst = src * imm32 (sign-extended). There is no imm64 form."}
  - {syntax: "IMUL r/m64", opcode: "REX.W + F7 /5", note: "One-operand form: RDX:RAX := RAX * r/m64, the signed counterpart of MUL."}
search_phrases:
  - multiply two integers
  - multiply a variable by a constant
  - multiply a register by an immediate
  - signed multiplication
  - multiply and keep only the low half of the product
  - multiply with any destination register
related: [mul, mulx, shl, lea, idiv]
---

## What it does

`imul` multiplies signed integers. It has three forms:

- **Two operands:** `imul dst, src` computes `dst = dst * src`, keeping only the low half (the product is truncated to the destination size).
- **Three operands:** `imul dst, src, imm` computes `dst = src * imm` without disturbing `src`.
- **One operand:** `imul src` is the signed twin of `mul`: `rdx:rax = rax * src`, the full 128-bit product.

## When to use it

- The everyday multiply of two integers, or of an integer by a constant.
- When you want the destination to be any register instead of being forced into `rax`/`rdx`.
- The one-operand form when you need the full signed 128-bit product.

## Gotchas

- **Truncating forms.** The two- and three-operand forms drop the high half, and CF/OF tell you whether that lost information (signed overflow). For a multiply that cannot overflow you can ignore them.
- **Same low bits as unsigned.** The low 64 bits of a product are identical for signed and unsigned operands, so `imul r64, r/m64` also works for unsigned values when you only need the low half. CF/OF then describe *signed* overflow, so use `mul` if you need unsigned overflow.
- **Immediates are sign-extended, at most 32 bits.** There is no `imul r64, r/m64, imm64`.
- **Only CF and OF are defined;** SF, ZF, AF and PF are undefined afterwards.
- **No 8-bit two- or three-operand forms.** Use the 16-, 32- or 64-bit registers.
- **32-bit operations zero the upper half** of the destination register.

## Example

```nasm
imul rax, rbx           ; rax = rax * rbx (low 64 bits)
imul rax, rbx, 10       ; rax = rbx * 10, rbx unchanged
imul rax, [rdi], -3     ; rax = the qword at [rdi] * -3
jo   .overflow          ; taken if the signed result did not fit

imul rbx                ; one-operand form: rdx:rax = rax * rbx (signed)
```
