---
slug: rax-rdx-implicit-operands
title: "RAX and RDX: the registers multiplication, division and sign extension insist on"
summary: Why mul and div take no register choice, how rdx:rax forms a 128-bit value, how to set it up before dividing, and the other instructions that quietly use RAX.
tags: [registers, rax, rdx, multiplication, division]
status: draft
related_instructions: [mul, imul, div, idiv, cqo, cdqe, cmpxchg, cmpxchg16b, stos, lods, scas, xlat, cpuid, mulx]
sdm_refs:
  - "Vol. 2, MUL—Unsigned Multiply (PDF pp. 1429-1430); IMUL—Signed Multiply (PDF pp. 1155-1158)"
  - "Vol. 2, DIV—Unsigned Divide (PDF pp. 968-970); IDIV—Signed Divide (PDF pp. 1152-1154)"
  - "Vol. 2, CBW/CWDE/CDQE; CWD/CDQ/CQO; CMPXCHG; CMPXCHG8B/CMPXCHG16B; LODS; STOS; SCAS; XLAT/XLATB; CPUID; RDTSC; MULX—Unsigned Multiply Without Affecting Flags (PDF pp. 1441-1442)"
extra_sources:
  - "Example code assembled with NASM 2.16.01 and run on Linux (x86-64): mulhi(0xFFFFFFFFFFFFFFFF, 2) = 1; divmod(-7, 2) gives quotient -3 and remainder -1."
search_phrases:
  - why does mul always use rax
  - which registers does div use
  - how do I set up rdx before dividing
  - what is cqo for
  - which instructions implicitly use the accumulator
  - how to get the high 64 bits of a multiplication
---

## Why these two

Multiplying two 64-bit numbers can produce a 128-bit result, and dividing needs a dividend at least as wide as the divisor times the quotient. The classic instructions solve both by fixing the registers: `rax` holds the 64-bit operand or half-result, and `rdx` holds the other 64 bits. That is why `mul rbx` takes a single operand: the other multiplicand is `rax`, and the product goes to `rdx:rax`.

## Multiplication

| Instruction | Inputs | Result |
|---|---|---|
| `mul src64` (also one-operand `imul`) | `rax` and `src` | `rdx:rax` (high half in `rdx`) |
| `mul src32` | `eax` and `src` | `edx:eax` (both zero-extended into `rdx`, `rax`) |
| `mul src8` | `al` and `src` | `ax` |

```nasm
mulhi:                          ; unsigned long mulhi(unsigned long a, unsigned long b)
        mov     rax, rdi        ; mul's implicit multiplicand is rax
        mul     rsi             ; rdx:rax = rax * rsi
        mov     rax, rdx        ; return the high 64 bits
        ret
```

`mul` always overwrites `rdx`, even if you only want the low half. If you do only want the low half, the two- and three-operand forms of `imul` let you choose the registers and leave `rdx` alone. `mulx` (BMI2) avoids `rax` and the flags, but it still takes `rdx` as its implicit multiplicand.

## Division

`div src` and `idiv src` divide the 128-bit value in `rdx:rax` by `src`: the quotient goes to `rax` and the remainder to `rdx`. Two preparation rules:

- **Unsigned:** zero the top half first, `xor edx, edx`.
- **Signed:** copy the sign of `rax` into every bit of `rdx` with **`cqo`**. Zeroing `rdx` instead would turn a negative dividend into a huge positive one.

```nasm
divmod:                         ; void divmod(long a, long b, long *quot, long *rem)
        mov     r8, rdx         ; idiv overwrites rdx, so park the 'quot' pointer in r8
        mov     rax, rdi        ; dividend
        cqo                     ; rdx:rax = rax sign-extended
        idiv    rsi             ; rax = quotient, rdx = remainder
        mov     [r8], rax
        mov     [rcx], rdx
        ret
```

Division raises `#DE` (a fault, not a flag) when the divisor is zero or when the quotient does not fit in `rax`. The classic overflow is the most negative 64-bit number divided by -1.

## Sign-extension helpers

- `cdqe` sign-extends `eax` into `rax`. It exists because a plain 32-bit write zero-extends.
- `cqo` copies the sign bit of `rax` into all of `rdx`, making the 128-bit dividend that `idiv` needs.
- The smaller forms are `cbw`/`cwde` and `cwd`/`cdq`.

## Other instructions that quietly use RAX

| Instruction | Role of `rax` (or `al`/`eax`) |
|---|---|
| `cmpxchg` | The comparand; on failure the memory value is loaded into it. `cmpxchg16b` uses `rdx:rax` instead. |
| `stos`, `scas`, `lods` | The data register: stored, compared with memory, or loaded from memory. |
| `xlat` | `al` is the index, and the looked-up byte replaces it. |
| `cpuid` | `eax` selects the leaf; results come back in `eax`, `ebx`, `ecx`, `edx`. |
| `rdtsc` | The time-stamp counter returns in `edx:eax`. |

Several arithmetic instructions also have a dedicated accumulator form: `add rax, imm32`, `sub rax, imm32` and `cmp rax, imm32` use an opcode with no ModRM byte, which makes them one byte shorter than the general form for a full 32-bit immediate (small immediates already have a compact `imm8` form).

## Conventions on top of the hardware

Both Linux and Windows return a function's integer result in `rax`. System V also uses `rdx` as the second integer return register (and the 3rd argument register); Windows uses `rdx` for the 2nd argument. On Linux `rax` additionally holds the **system call number** before `syscall`. Details in the calling-convention articles: [Linux](/articles/abi-system-v-linux), [Windows](/articles/abi-microsoft-x64-windows).

Instruction pages: [MUL](/instructions/mul), [IMUL](/instructions/imul), [DIV](/instructions/div), [IDIV](/instructions/idiv).
