---
slug: cpu-exceptions
title: "CPU exceptions: what #UD, #DE, #GP, #PF and the others are, and what the CPU does"
summary: What an x86 exception is, what the CPU does when one happens, which ones a user program can cause (#UD, #DE, #GP, #PF, #SS, #AC, #BP) and how Linux turns them into signals. Verified with real programs.
tags: [exceptions, faults, ud, gp, pf, interrupts]
status: draft
related_instructions: [div, idiv, ud2, int, lock, popcnt, cpuid, endbr64, push, pop, mov, syscall]
sdm_refs:
  - "Vol. 3A, Chapter 7 Interrupt and Exception Handling (PDF pp. 3351-3411): 7.1-7.6 overview, vectors and classes (Table 7-1), 7.8 masking, 7.12-7.14 delivery and 64-bit mode, 7.15 the per-exception reference"
  - "Vol. 1, 3.3.7.1 Canonical Addressing (PDF p. 76)"
  - "Vol. 2: UD—Undefined Instruction (PDF p. 2026), DIV (PDF pp. 968-970), INT n/INTO/INT3/INT1 (PDF pp. 1171-1186), HLT (PDF p. 1143), DAA (PDF pp. 962-963)"
extra_sources:
  - "Linux behaviour observed with tests/asm/exceptions.asm and test_exceptions.c: GCC 12.2 and NASM 2.16.01 on Debian 12, run in Docker on the host's Linux kernel (x86-64). Every case runs in its own child process; the handler prints the signal, its code, and the CPU's vector number and error code taken from the signal context (REG_TRAPNO, REG_ERR). The signals are Linux's choice, not the CPU's."
  - "Not run or covered: other operating systems, real Windows, interrupts and NMI, machine checks, virtualization, and the x87/SIMD exceptions (#NM, #MF, #XM)."
search_phrases:
  - what is a #UD invalid opcode exception
  - what does general protection fault mean on x86
  - what happens when the cpu raises an exception
  - difference between a fault, a trap and an abort
  - why does my program get sigsegv or sigill on x86
  - what is a page fault and what is the error code
  - program killed by SIGFPE on an integer divide
---

An **exception** is the processor stopping an instruction because it found something wrong with it: a division by zero, an opcode that does not exist, a memory access that is not allowed. The operating system gets to react, and the program usually either carries on or is ended. This page explains what the CPU does, which exceptions a user-space program can cause, and what Linux shows you when one happens.

## Exceptions and interrupts

Both are *events* that suspend the running program and call a handler. **Interrupts** come from outside the instruction stream: a device or the `int n` instruction. **Exceptions** come from the instruction being executed. Each event has a **vector number** from 0 to 255. Vectors 0 to 31 are reserved by the architecture; the rest are free for devices and software.

The usual written form is `#` followed by two letters: `#UD` is vector 6, `#GP` is 13, `#PF` is 14. The `IF` flag, which `cli` and `sti` change, switches off external interrupts only; it never hides an exception.

## What the CPU does

1. **It notices the problem** while executing the instruction. Apart from aborts, an exception is reported on an instruction boundary: the program is never left half way through an instruction.
2. **It finds the handler.** The vector is an index into the *interrupt descriptor table* (IDT) that the operating system filled in. In 64-bit mode each entry is 16 bytes, so the entry for vector 14 is 14 x 16 bytes into the table.
3. **It saves where it was.** It pushes the stack pointer (`ss:rsp`), `rflags` and the return address (`cs:rip`) on a stack the operating system provides, each as 8 bytes. In 64-bit mode `ss:rsp` is always pushed. Some exceptions push one more value on top, the **error code**.
4. **It calls the handler,** which is operating-system code. Your program is suspended until the handler finishes.
5. **The handler decides.** It can repair the cause and resume the program with `iret`, or give up and end the process.

Resuming goes back to the saved `cs:rip`. Whether that is the instruction that failed or the one after it depends on the class of the exception.

## Fault, trap or abort

| Class | The saved `rip` points at | Can the program go on? | Examples |
|---|---|---|---|
| **Fault** | the instruction that caused it, with the machine state as it was before the instruction started | yes: once the cause is fixed, that instruction runs again | `#DE`, `#UD`, `#GP`, `#PF` |
| **Trap** | the instruction after the one that caused it | yes, from there | `#BP` (`int3`) |
| **Abort** | not always the exact instruction | no | `#DF`, `#MC` |

This is why a page fault is usually invisible: the operating system loads the missing page and the CPU runs the same load again. It is also why a division by zero cannot simply be resumed: the same `div` would fault again, so the system ends the program or runs a handler you installed.

## The exceptions a user program can cause

| Vector | Name | Class | Error code | What triggers it in your code |
|---|---|---|---|---|
| 0 | `#DE` divide error | fault | no | `div` or `idiv` with a zero divisor, or a quotient that does not fit in the destination |
| 1 | `#DB` debug | fault or trap | no | single-stepping (`TF` set) and hardware breakpoints |
| 3 | `#BP` breakpoint | trap | no | `int3` |
| 6 | `#UD` invalid opcode | fault | no | an undefined or reserved opcode, `ud2`, a `lock` prefix on something that cannot be locked, an instruction the CPU does not support, an instruction that is not valid in 64-bit mode |
| 8 | `#DF` double fault | abort | yes, always zero | a second exception while the CPU was delivering the first one |
| 12 | `#SS` stack fault | fault | yes | a stack access that fails, for instance through a non-canonical `rsp` |
| 13 | `#GP` general protection | fault | yes | a non-canonical address, a privileged instruction at user level, a misaligned 16-byte SSE operand, `int n` to a gate user code may not call |
| 14 | `#PF` page fault | fault | yes, special layout | a page that is not present, a write to a read-only page, a fetch from a no-execute page |
| 17 | `#AC` alignment check | fault | yes, normally zero | a misaligned data access, only at user level with the alignment-check flag set |
| 18 | `#MC` machine check | abort | no | a hardware error: an internal machine error or a bus error |
| 21 | `#CP` control protection | fault | yes, special layout | a `ret` that does not match the shadow stack, or a missing `endbr64` where an indirect branch lands, when that protection is enabled |

Vector 4 (`#OF`) comes from `into` and vector 5 (`#BR`) from `bound`. Neither instruction can be used in 64-bit mode, so a 64-bit program does not meet them; the opcode of `into` gives `#UD`.

### #UD: the CPU will not run this

The invalid-opcode exception is the CPU's answer to "that is not an instruction I can execute here". It has no error code and the saved `rip` points at the offending instruction. Causes you meet in practice:

- **A real undefined opcode,** or `ud2`, which exists to raise this exception on purpose, for software testing.
- **A `lock` prefix on an instruction that cannot be locked,** or on one that can be locked but whose destination is not memory (`lock add eax, ebx`).
- **An instruction that was removed in 64-bit mode,** such as the old BCD adjust `daa` (opcode `27`) or `into` (opcode `CE`).
- **An instruction for a CPU feature this CPU lacks,** such as [POPCNT](/instructions/popcnt) on a processor whose CPUID does not report it.

### #DE: a division that cannot be done

[DIV](/instructions/div) and [IDIV](/instructions/idiv) raise it when the divisor is zero and also when the quotient does not fit in the register that must receive it. The second case surprises people:

```nasm
        mov     edx, 1                   ; dividend = 1:0 = 2^64
        xor     eax, eax
        mov     ecx, 1
        div     rcx                      ; the quotient 2^64 does not fit in rax: #DE
```

For `idiv` the classic overflow is the most negative 64-bit number divided by -1, whose true quotient is +2^63. A divide error is reported through the exception, never through a flag, so there is nothing to test afterwards.

### #GP and #PF: two ways to be refused memory

- **`#PF`** is about the *page tables*. The CPU found no usable translation for the address: the page is not present, the access type is not allowed (a write to a read-only page, a fetch from a no-execute page), or user code touched a page reserved for the kernel. The CPU puts the faulting address in the `cr2` register and describes the access in the error code, so the handler can see *what* you tried to do.
- **`#GP`** is every other protection violation. The usual user-mode causes are an address that is not **canonical** (bits 63 down to 48 must all equal bit 47), a **privileged instruction** such as `hlt`, `cli` or `in`, a **misaligned** 16-byte SSE operand such as `movaps`, and `int n` for a vector whose gate user code may not call. The error code is normally zero.

The page-fault error code is a set of bits. Bit 0 clear means "page not present"; bit 1 means the access was a write; bit 2 means it came from user mode; bit 4 means it was an instruction fetch.

The error code of a `#GP` or `#SS` that involves a descriptor has a different layout: bit 0 says the event was external, bit 1 says the index refers to the IDT, bit 2 chooses the LDT over the GDT, and bits 15:3 are the index. After `int 0x21` the CPU reports vector 13 with error code `0x10a`: the index 0x21 shifted left by 3 gives `0x108`, and the IDT flag adds 2.

### #BP and #DB: how debuggers stop your program

A debugger sets a breakpoint by overwriting the first byte of an instruction with `int3`, the one-byte opcode `CC`. When it runs, `#BP` is a trap, so the saved `rip` points *after* the `int3`; the debugger puts the original byte back, subtracts one from the saved `rip` and resumes. Single-stepping uses the `TF` flag in `rflags`: after each instruction the CPU raises `#DB`.

### #AC, #SS, #DF, #CP

`#AC` fires only when three things are true: the alignment-check bit in `cr0` is set by the operating system, the `AC` flag in `rflags` is set (a user program can set it with `popf`), and the program is running at user level. Alignment is checked on data accesses, not on instruction fetches. `#SS` is the stack's version of `#GP`; in 64-bit mode the usual cause is a non-canonical `rsp`. `#DF` means a second exception happened while the CPU was delivering the first; it cannot be resumed, and the SDM says an application that causes an abort should be ended by the operating system. `#CP` belongs to Intel's control-flow enforcement: `ret` against a shadow stack, or an indirect call or jump that lands somewhere other than an `endbr64`.

## What Linux makes of them

The CPU only knows vectors. The kernel's handler turns most exceptions that came from user mode into a **signal** sent to the process. The program in `tests/asm/test_exceptions.c` provokes each one in a child process and prints what arrives, including the vector and error code Linux passes along in the signal context. Measured on x86-64 Linux:

| You executed | CPU vector | Error code | Signal | `si_code` |
|---|---|---|---|---|
| `ud2`, `lock add eax, ebx`, byte `27h`, byte `CEh` | 6 `#UD` | 0 | `SIGILL` | `ILL_ILLOPN` |
| `div` by zero, `div` with a quotient that is too big, `idiv` of the most negative number by -1 | 0 `#DE` | 0 | `SIGFPE` | `FPE_INTDIV` |
| `int3` | 3 `#BP` | 0 | `SIGTRAP` | `SI_KERNEL` |
| a read from address 0 | 14 `#PF` | `0x4` | `SIGSEGV` | `SEGV_MAPERR`, address 0 |
| a jump to address 0 (`call rax` with `rax` = 0) | 14 `#PF` | `0x14` | `SIGSEGV` | `SEGV_MAPERR`, address 0 |
| a write to a read-only page | 14 `#PF` | `0x7` | `SIGSEGV` | `SEGV_ACCERR`, the address |
| a read from a non-canonical address | 13 `#GP` | 0 | `SIGSEGV` | `SI_KERNEL`, no address |
| `movaps` on an address that is not 16-byte aligned | 13 `#GP` | 0 | `SIGSEGV` | `SI_KERNEL`, no address |
| `hlt`, `cli`, `in al, dx` | 13 `#GP` | 0 | `SIGSEGV` | `SI_KERNEL`, no address |
| `int 0x21` | 13 `#GP` | `0x10a` | `SIGSEGV` | `SI_KERNEL`, no address |
| `push` with a non-canonical `rsp` | 12 `#SS` | 0 | `SIGBUS` | `SI_KERNEL` |
| an unaligned load with `rflags.AC` set | 17 `#AC` | 0 | `SIGBUS` | `BUS_ADRALN` |

So **the signal alone does not tell you which exception happened**: `SIGSEGV` covers both `#PF` and `#GP`, and `SIGBUS` covers both `#SS` and `#AC`. In the cases above two details separate them: a `SIGSEGV` with `SEGV_MAPERR` or `SEGV_ACCERR` is a page fault and comes with the faulting address, while a `SIGSEGV` with `SI_KERNEL` is a general-protection fault, which has no address to report. `SEGV_MAPERR` says no page is mapped there; `SEGV_ACCERR` says a page is mapped but the access is not allowed.

When a program receives one of these signals and has no handler for it, the process is ended by that signal; the test confirms it for `ud2` and for a read from address 0. Your own `sigaction` handler, as in the test program, can look at the same information before that happens.

## Reading a crash

- **`SIGILL`:** look at the instruction at the reported address. A `ud2`, a missing CPU feature (an instruction newer than the machine), or jumping into data are the usual reasons.
- **`SIGFPE` in integer code:** a `div` or `idiv` fault, even though no floating-point instruction is involved. Check for a zero divisor and for a dividend that was not set up (`rdx` left over, or `cqo` missing).
- **`SIGSEGV` with an address:** you used a bad pointer. Address 0 or a small number is a null pointer; a large garbage number is a corrupted pointer or a use after free.
- **`SIGSEGV` with no address:** a general-protection fault: a non-canonical pointer (often a corrupted pointer whose upper bits are junk), a privileged instruction, or a misaligned SSE access, which is the classic result of a stack that was not 16-byte aligned at a `call` (see [RSP and RBP](/articles/rsp-rbp-stack-and-frame)).
- **`SIGBUS`:** in these tests, a stack fault or an alignment check.

## Where the instruction pages say which exceptions apply

The SDM lists the exceptions an instruction can raise at the end of its entry, per mode. The pages on this site mention the ones that matter for user code: [DIV](/instructions/div) and [IDIV](/instructions/idiv) (`#DE`), [PUSH](/instructions/push) and [POP](/instructions/pop) (`#SS`, `#GP` and `#PF` for the stack memory they touch, `#UD` for a `lock` prefix), [MOV](/instructions/mov) (`#GP` for a non-canonical address, `#UD` for loading `cs` or using `lock`) and [POPCNT](/instructions/popcnt) (`#UD` without the CPUID feature).

This page covers what Linux does because that is what was run. Other operating systems report the same CPU exceptions in their own way; they are not covered here, and neither are device interrupts, `NMI`, machine checks, virtualization exceptions or the x87 and SIMD floating-point exceptions.
