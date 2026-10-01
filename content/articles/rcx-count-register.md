---
slug: rcx-count-register
title: "RCX: the count register, and what ECX and CL can do that no other register can"
summary: Variable shift counts must be in CL, LOOP, REP and JRCXZ count in RCX, and SYSCALL overwrites RCX. A precise list of RCX's jobs, plus the BMI2 way around it.
tags: [registers, rcx, shifts, loops]
status: draft
related_instructions: [shl, shr, sar, rol, ror, rcl, rcr, shld, shrd, shlx, shrx, sarx, loop, rep, jcc, syscall, cpuid, rdtscp, cmpxchg16b]
sdm_refs:
  - "Vol. 2, SAL/SAR/SHL/SHR—Shift (PDF pp. 1892-1896): count in CL, masked to 5 bits, or 6 bits with REX.W"
  - "Vol. 2, RCL/RCR/ROL/ROR—Rotate (PDF pp. 1822-1826); SHLD (PDF pp. 1929-1931): CL forms"
  - "Vol. 2, SARX/SHLX/SHRX—Shift Without Affecting Flags (PDF pp. 1898-1899)"
  - "Vol. 2, LOOP/LOOPcc (PDF pp. 1274-1276); Jcc (JRCXZ, PDF pp. 1203-1207); REP (count register is RCX in 64-bit mode)"
  - "Vol. 2, SYSCALL (RCX := RIP, R11 := RFLAGS); CPUID (EAX leaf, ECX sub-leaf); RDTSCP (ECX := IA32_TSC_AUX); CMPXCHG8B/CMPXCHG16B (RCX:RBX)"
extra_sources:
  - "System V AMD64 ABI draft 0.99.6, Appendix A.2 (Linux kernel conventions): the kernel interface passes the 4th argument in r10, and 'the kernel destroys registers %rcx and %r11'."
  - "Example code assembled with NASM 2.16.01 and run on Linux (x86-64): shl_by(3,4) = 48; fill_bytes and copy_bytes via rep stosb / rep movsb."
  - "Wikibooks, 'x86 Assembly/Print Version', sections 'Loop Instructions' and 'Jump if counter register is zero' (CC BY-SA): used as a map; its ECX-only wording was corrected for 64-bit mode against the SDM."
search_phrases:
  - which register holds the shift count
  - why must the shift amount be in cl
  - what is ecx used for in x86
  - which register is the loop counter
  - what does rcx do in x86-64
  - which registers does the syscall instruction overwrite
---

## The short answer

`rcx` is the one register hard-wired as a **count**. Five things only RCX, ECX or CL can do:

1. Supply a **variable shift or rotate count** (as `cl`).
2. Count iterations for `loop`, `loope`, `loopne`, the `rep` string prefixes and `jrcxz`.
3. Be **silently overwritten by `syscall`**.
4. Carry the **sub-leaf number into `cpuid`** (and return `IA32_TSC_AUX` from `rdtscp`).
5. Hold the high half of the replacement value in `cmpxchg16b` (the pair `rcx:rbx`).

For everything else `rcx` is an ordinary register.

## 1. Variable shifts and rotates need CL

The shifts (`shl`, `shr`, `sar`), the rotates (`rol`, `ror`, `rcl`, `rcr`) and the double shifts (`shld`, `shrd`) have a form that takes the count from a register, and that register can only be **`cl`**. An immediate count or the constant 1 needs no register at all, but a count that is only known at run time has to be moved into `cl` first:

```nasm
shl_by:                         ; unsigned long shl_by(unsigned long x, unsigned long n)
        mov     rax, rdi        ; x
        mov     ecx, esi        ; a variable shift count must be in CL
        shl     rax, cl
        ret
```

- The count is masked: only the low **6 bits** of `cl` are used for a 64-bit operand (low 5 bits for 32-bit and smaller). `shl rax, cl` with `cl = 64` shifts by 0.
- Whatever else was in `rcx` is needed again afterwards, so save it: the shift pins down `rcx` for its duration.
- **The way around it is BMI2.** `shlx`, `shrx` and `sarx` take the count from *any* general-purpose register and do not touch the flags. They exist only on processors with BMI2, so check CPUID before relying on them.

## 2. RCX counts for loop, rep and jrcxz

- `loop` decrements `rcx` and jumps back while it is not zero. `loope` and `loopne` also test ZF. The decrement happens before the test, so `rcx = 0` on entry means 2^64 iterations.
- `rep movsb`, `rep stosb` and friends repeat the string instruction `rcx` times.
- `jrcxz` jumps if `rcx` is zero and is the usual guard in front of a `loop` or `rep`.

In 64-bit mode the counter is `rcx`. Only with a `67h` address-size prefix does it become `ecx`, so `mov ecx, 10` (which also zeroes the top half) is the normal way to load a small count:

```nasm
fill_bytes:                     ; void fill_bytes(void *dst, int byte, size_t n)
        mov     rcx, rdx        ; rep uses rcx as its repeat count
        mov     eax, esi        ; stosb stores AL
        rep stosb               ; repeat rcx times: [rdi] = al, rdi += 1
        ret
```

## 3. syscall overwrites RCX (and R11)

`syscall` saves the address of the following instruction in `rcx` and the flags in `r11`, then enters the kernel. Both registers are therefore lost across every `syscall`; do not keep anything in them. This is also why the Linux kernel takes its fourth argument in `r10` instead of `rcx`, unlike an ordinary function call, where the fourth argument is in `rcx`.

## 4. cpuid and rdtscp

`cpuid` reads the leaf from `eax` and, for some leaves, the sub-leaf from `ecx`, and returns results in `eax`, `ebx`, `ecx` and `edx`. `rdtscp` returns the time-stamp counter in `edx:eax` and `IA32_TSC_AUX` in `ecx`.

## 5. cmpxchg16b

The 16-byte atomic compare-and-exchange compares `rdx:rax` with memory and, on a match, stores `rcx:rbx`.

## Gotchas

- **Conflicts are the real cost.** Code that shifts by a variable amount inside a `rep` or `loop` body must juggle `rcx`: save the count, load `cl`, shift, restore.
- **Calling conventions already use `rcx`.** On Linux it carries the 4th argument; on Windows the 1st. A function that needs a shift count in `cl` often has to move its own arguments first.
- **8-bit `cl` only reaches the low byte** and leaves the rest of `rcx` untouched, whereas writing `ecx` clears the upper half.

Instruction pages: [SHL](/instructions/shl), [SHR](/instructions/shr), [SAR](/instructions/sar), [LOOP](/instructions/loop), [Jcc and JRCXZ](/instructions/jcc).
