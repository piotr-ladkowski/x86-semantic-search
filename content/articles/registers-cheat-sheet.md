---
slug: registers-cheat-sheet
title: The 16 general-purpose registers and what each one is for
summary: Register names at every size, which instructions give RAX, RCX, RDX, RSI, RDI, RSP and RBP built-in jobs, and where the registers really are interchangeable.
tags: [registers, 64-bit-mode, cheat-sheet]
status: draft
related_instructions: [mov, mul, div, cqo, cdqe, shl, loop, rep, movs, stos, push, pop, syscall, cpuid, cmpxchg16b, xlat, leave]
sdm_refs:
  - "Vol. 1, section 3.4.1.1 General-Purpose Registers in 64-Bit Mode (PDF pp. 78-79)"
  - "Vol. 2 entries: MUL, IMUL, DIV, IDIV, CBW/CWDE/CDQE, CWD/CDQ/CQO, CMPXCHG, CMPXCHG8B/CMPXCHG16B, XLAT/XLATB, MOVS, STOS, LODS, SCAS, REP, LOOP/LOOPcc, SAL/SAR/SHL/SHR, SYSCALL, CPUID, RDTSC, LEAVE, PUSH, POP"
extra_sources:
  - "Register names verified by assembling every form with NASM 2.16.01; NASM rejects mov ah, sil with 'cannot use high byte register in rex instruction'."
  - "Preserved-register lists: System V AMD64 ABI draft 0.99.6 (section 3.2.1) and Microsoft 'x64 Calling Convention' documentation."
  - "Wikibooks, 'x86 Assembly/Print Version', section 'General-purpose registers (64-bit naming conventions)' (CC BY-SA): used as a map of the topic."
search_phrases:
  - which registers have special roles in x86-64
  - what is the difference between rax rbx rcx and rdx
  - names of the 8-bit, 16-bit and 32-bit parts of a register
  - which register should I use for what
  - are all general purpose registers equal
---

## The 16 registers and their names

Each register can be used at four widths, each with its own name:

| 64-bit | 32-bit | 16-bit | low byte | high byte |
|---|---|---|---|---|
| `rax` | `eax` | `ax` | `al` | `ah` |
| `rbx` | `ebx` | `bx` | `bl` | `bh` |
| `rcx` | `ecx` | `cx` | `cl` | `ch` |
| `rdx` | `edx` | `dx` | `dl` | `dh` |
| `rsi` | `esi` | `si` | `sil` | - |
| `rdi` | `edi` | `di` | `dil` | - |
| `rbp` | `ebp` | `bp` | `bpl` | - |
| `rsp` | `esp` | `sp` | `spl` | - |
| `r8` ... `r15` | `r8d` ... `r15d` | `r8w` ... `r15w` | `r8b` ... `r15b` | - |

Three rules that catch people out:

- **Writing a 32-bit name clears the upper 32 bits; writing an 8- or 16-bit name leaves the rest alone.** See [Why writing EAX clears the top half of RAX](/articles/partial-register-writes).
- **`r8`-`r15`, `sil`, `dil`, `bpl` and `spl` can only be reached through a REX prefix.** With any REX prefix, `ah`, `bh`, `ch` and `dh` cannot be encoded (the same bits mean `spl`, `bpl`, `sil`, `dil`), so one instruction cannot mix `ah` with `sil` or `r8b`. NASM rejects it: `mov ah, sil` fails with "cannot use high byte register in rex instruction".
- **There is no separate name for the upper part of a register.** To get at bits 63:32 you shift (`shr rax, 32`).

## Registers with a built-in job

For ordinary arithmetic, loads and stores every register is equal. The differences below come from specific instructions that name a register implicitly, so you cannot choose another one.

| Register | Built-in job | Instructions |
|---|---|---|
| `rax` | Accumulator: implicit multiplicand, dividend, comparand and string-data register | `mul`, `imul` (one operand), `div`, `idiv`, `cdqe`, `cqo`, `cmpxchg`, `stos`, `lods`, `scas`, `xlat`, `cpuid`, `rdtsc` |
| `rbx` | Almost none in 64-bit mode: table base for `xlat`, low half of the new value for `cmpxchg16b` | `xlat`, `cmpxchg16b` |
| `rcx` | Counter: `cl` holds variable shift counts, `rcx` counts `loop`, `rep` and `jrcxz`; `syscall` overwrites it | `shl`, `shr`, `sar`, `rol`, `ror`, `rcl`, `rcr`, `shld`, `shrd`, `loop`, `rep`, `jrcxz`, `syscall` |
| `rdx` | High half of a 128-bit value: product of `mul`, dividend and remainder of `div`, result of `cqo` | `mul`, `div`, `idiv`, `cqo`, `cpuid`, `rdtsc` |
| `rsi` | Source pointer of the string instructions | `movs`, `lods`, `cmps` |
| `rdi` | Destination pointer of the string instructions | `movs`, `stos`, `scas`, `cmps` |
| `rsp` | The stack pointer | `push`, `pop`, `call`, `ret`, `leave` |
| `rbp` | A frame pointer by convention; `leave` restores it, otherwise an ordinary register | `leave`, `enter` |
| `r8` ... `r15` | No built-in job, except that `syscall` saves RFLAGS in `r11` | `syscall` |

Deeper dives: [RCX](/articles/rcx-count-register), [RAX and RDX](/articles/rax-rdx-implicit-operands), [RSI and RDI](/articles/rsi-rdi-string-registers), [RSP and RBP](/articles/rsp-rbp-stack-and-frame).

## Choosing registers without conflicts

- Keep a value you still need out of the register an instruction is about to overwrite: `rax` and `rdx` around `mul`/`div`, `rcx` around shifts, `loop`, `rep` and `syscall`, `rsi` and `rdi` around string instructions, `r11` around `syscall`.
- `r8`-`r15` and `rbx` are the "quiet" registers no instruction forces on you (apart from the few uses above), which makes them good homes for values that live long. `r8`-`r15` need a REX prefix, which adds a byte unless the instruction already has one (64-bit operations always do).
- The operating system's calling convention decides which registers survive a function call. Both Linux and Windows preserve `rbx`, `rbp`, `rsp` and `r12`-`r15`; Windows also preserves `rdi` and `rsi`. Details: [System V (Linux)](/articles/abi-system-v-linux) and [Microsoft x64 (Windows)](/articles/abi-microsoft-x64-windows).
