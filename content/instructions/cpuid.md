---
slug: cpuid
mnemonic: CPUID
aliases: []
title: CPU Identification
summary: Returns the processor's vendor, model and supported features in EAX, EBX, ECX and EDX, for the leaf chosen by EAX (and ECX).
category: miscellaneous
status: draft
cpuid_feature: null
sdm_entries: ["CPUID—CPU Identification"]
extra_sources:
  - "System V AMD64 ABI 0.99, section 3.2.1 (rbx is preserved for the caller); Microsoft Learn, x64 calling convention, \"Caller/callee saved registers\" (RBX is nonvolatile)."
  - "GCC manual, \"x86 Built-in Functions\" (__builtin_cpu_supports) and GCC's <cpuid.h> (__get_cpuid_count); both run with GCC 12.2 in tests/asm/test_cpuid.c."
  - "Microsoft Learn, \"__cpuid, __cpuidex\" (<intrin.h>; not run)."
flags:
  note: "No flags are affected."
forms:
  - {syntax: "CPUID", opcode: "0F A2", note: "No explicit operands. Reads EAX (the leaf) and, for some leaves, ECX (the sub-leaf); writes EAX, EBX, ECX and EDX, and clears the upper 32 bits of RAX, RBX, RCX and RDX."}
search_phrases:
  - detect CPU features at runtime
  - check if the processor supports an instruction set extension
  - get the CPU vendor string
  - read the processor brand name
  - find the CPU family, model and stepping
  - serializing instruction allowed in user mode
related: [popcnt, lzcnt, mulx, movbe, rdrand, rdtscp, rdtsc]
---

## What it does

`cpuid` reports identification and feature information about the processor that runs it. The value in `eax` selects a *leaf* (which question to answer) and, for leaves that are split into sub-leaves, `ecx` selects the sub-leaf. The answer is written to `eax`, `ebx`, `ecx` and `edx`. It works at any privilege level, so ordinary user code uses it to find out which instructions it may execute.

The leaves you need most:

| `eax` in | `ecx` in | What comes back |
|---|---|---|
| `0` | ignored | `eax` = highest basic leaf; `ebx`, `edx`, `ecx` = vendor string, such as `GenuineIntel` |
| `1` | ignored | `eax` = family, model and stepping; `ecx` and `edx` = feature bits, for example `ecx` bit 13 CMPXCHG16B, 22 MOVBE, 23 POPCNT, 30 RDRAND |
| `7` | `0` | `eax` = highest sub-leaf; `ebx` = feature bits, for example bit 3 BMI1, 8 BMI2, 18 RDSEED, 19 ADX |
| `0x80000000` | ignored | `eax` = highest extended leaf |
| `0x80000001` | ignored | `ecx` bit 0 LAHF/SAHF in 64-bit mode, bit 5 LZCNT; `edx` bit 27 RDTSCP |
| `0x80000002` to `0x80000004` | ignored | The processor brand string, 16 bytes per leaf in `eax`, `ebx`, `ecx`, `edx` order, 48 bytes in all |

## When to use it

- Choosing a code path once at startup: check whether the CPU has POPCNT, LZCNT, BMI2, ADX and the like, then use the fast instructions or a fallback.
- Identifying the processor for logs and bug reports: vendor string, brand string, family and model.
- Serializing execution from user code: `cpuid` is one of the few serializing instructions allowed outside the kernel. Where CPUID reports the `serialize` instruction (leaf 7, `edx` bit 14), the SDM prefers that one.
- From C or C++, call the compiler's wrapper instead of writing assembly: GCC's `__builtin_cpu_supports("bmi2")` or `__get_cpuid_count` from `<cpuid.h>`, or MSVC's `__cpuidex(info, leaf, subleaf)` from `<intrin.h>`.

## Gotchas

- **It overwrites `rbx`, which your caller expects to keep.** Both the System V and the Microsoft x64 conventions make `rbx` callee-saved, so a function that runs `cpuid` must save and restore it. All four registers are written in full: the upper halves of `rax`, `rbx`, `rcx` and `rdx` are cleared.
- **Set `ecx` as well as `eax`.** Leaf 7 and the other leaves with sub-leaves read `ecx`, so whatever is left in it picks the sub-leaf. A sub-leaf number above the maximum returns all zeros, and BMI2 or ADX then look absent. Clear `ecx` before asking for leaf 7.
- **Check the highest leaf first.** Leaf 0 reports the highest basic leaf and leaf `0x80000000` the highest extended one. Asking for a leaf above the maximum does not return zeros: you get the data of the highest basic leaf instead, which can look like real feature bits.
- **The vendor string comes back in `ebx`, `edx`, `ecx` order,** not `ebx`, `ecx`, `edx`. Store the registers in that order to get `GenuineIntel`. The bit meanings on this page are Intel's; the SDM tells software to identify the vendor before interpreting feature bits.
- **Family and model have extended fields.** In leaf 1 `eax`, the model in bits 7-4 is only the low part: for family 6 or 15, the extended model in bits 19-16 is the high part. For family 15, the extended family in bits 27-20 is added to the family.
- **A feature bit says the CPU has a feature, not that the OS enabled it.** For AVX the SDM's check has three steps: OSXSAVE (leaf 1, `ecx` bit 27), then `xgetbv` to confirm the OS enabled the YMM state, then the AVX bit. Integer extensions such as POPCNT and BMI2 need only their own bit.
- **Call it once and keep the answer.** In a virtual machine every `cpuid` is a VM exit into the hypervisor. And although `cpuid` serializes, the SDM's RDTSC entry orders `rdtsc` with `lfence`, not with `cpuid`.
- **Some fields differ between cores.** Instruction feature bits such as POPCNT or BMI2 are the same on every logical processor of a correctly configured system, but a field such as the initial APIC ID (leaf 1, `ebx` bits 31-24) belongs to one logical processor. The OS can move your thread to another core right after `cpuid` returns.
- A `lock` prefix raises `#UD`.

## Example

```nasm
has_bmi2:                       ; int has_bmi2(void): 1 if this CPU has BMI2, else 0
        push    rbx             ; cpuid overwrites rbx, which the caller expects preserved
        xor     eax, eax        ; leaf 0
        cpuid                   ; eax = highest basic leaf
        mov     r8d, eax
        xor     eax, eax        ; answer 0 ...
        cmp     r8d, 7
        jb      .done           ; ... if leaf 7 does not exist
        mov     eax, 7          ; leaf 7
        xor     ecx, ecx        ; sub-leaf 0: cpuid reads ecx for this leaf
        cpuid
        mov     eax, ebx
        shr     eax, 8
        and     eax, 1          ; eax = bit 8 of ebx (BMI2)
.done:  pop     rbx
        ret
```
