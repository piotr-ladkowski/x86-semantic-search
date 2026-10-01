# Scope

Read this before adding, removing or reclassifying any instruction. The machine-readable form of
this document is `content/roster.yaml`; if the two disagree, fix them together.

## Product

A web app where anyone types what they want to do in plain English ("count the set bits in a
register") and is shown the right x86-64 instruction with the essentials for using it: its forms,
the flags it touches, gotchas, and a short example. One small page per instruction. A few short
articles cover ideas that span several instructions (these are rarer than instruction pages).

The audience is a programmer who can read assembly but does not know the instruction they need.
Pages are **orientation, not a reference**: the Intel SDM stays the authority and every page names the
SDM entry it was checked against.

## v1 scope

> **x86-64 long mode, user-space, scalar integer / general-purpose instructions.**

Each qualifier is defined so it can be tested mechanically:

| Qualifier | Meaning | How to check in the SDM |
|---|---|---|
| **x86-64 long mode** | 64-bit mode of Intel 64 (a.k.a. IA-32e mode, `CS.L=1`). Pages describe 64-bit operand/address-size behaviour (default operand size 32 bits, REX prefixes, RIP-relative addressing). Compatibility mode, protected mode and real mode are **not** documented. | The opcode table's **"64-bit Mode"** column must say `Valid` for at least one form. Forms marked `Inv.` or `N.E.` are omitted from the page's `forms`. |
| **user-space** | Executable at privilege level 3 (CPL 3) in a normal OS environment, without the OS having to enable anything special. | The "Protected Mode Exceptions" section must not list `#GP(0)` *"if the current privilege level is not 0"* (or a `CR4`/`CR0` gate that a normal OS leaves closed). |
| **scalar integer / general-purpose** | Operates on general-purpose registers (`RAX`..`R15`), memory, `RFLAGS` and `RIP`. Includes VEX-encoded instructions that use *only* GPRs (BMI1/BMI2, `LZCNT`). | Operands are `r8/16/32/64`, `r/m*`, `imm*`, `m` and flags. Anything with `xmm`, `ymm`, `zmm`, `mm`, `st(i)`, mask registers or tile registers is out. |

## Inclusion test (apply in order)

For a candidate instruction, stop at the first rule that matches:

1. **Not valid in 64-bit mode** (BCD adjusts `AAA`/`DAA`, `PUSHA`, `BOUND`, `LDS`, ...) ->
   `excluded`, reason `invalid-in-64-bit-mode`.
2. **Needs CPL 0 / system programming** (`IN`/`OUT`, `CLI`/`STI`, `HLT`, `WRMSR`, `LGDT`, `IRET`, ...) ->
   `excluded`, reason `privileged`. All system-programming instructions (MSR access, VMX, SGX supervisor leaves, ...) are excluded.
3. **Loads or manipulates segment registers** (`LFS`/`LGS`/`LSS`, `MOV Sreg`) ->
   `excluded`, reason `segmentation` (segmentation is flat in long mode).
4. **Uses vector / x87 / MMX / AMX state** -> `excluded`, reason `non-scalar-or-non-integer`.
   **Saves or restores extended state** (`XSAVE`, `FXSAVE`) -> `excluded`, reason `extended-state`.
5. **Passes all of the above** -> `instructions` in the roster (in scope).
6. **You are unsure** -> put it under `deferred` with a one-line reason and tell the owner. Do **not**
   write a page for a `deferred` or `excluded` instruction. `docx86 validate` rejects pages whose
   slug is not in the roster `instructions` list.

The exclusion reasons are a closed set (see `ExcludedEntry` in `src/docx86/models.py`). The SDM's
own Vol. 1 section 5.1 ("General-Purpose Instructions", 16 subgroups) was the starting taxonomy and is
the source of the `category` values, but it still lists 32-bit-only instructions, so rule 1 must always
be applied.

## Decisions already made

| Decision | Choice | Why |
|---|---|---|
| `SYSCALL`, `INT n`/`INT3`, `CPUID`, `RDTSC`/`RDTSCP`, `PAUSE`, `RDRAND`/`RDSEED`, `ENDBR64`, `LOCK` | **In scope** | Ring-3 executable, GPR-based, and what people actually look up when reading compiler output or writing a syscall. |
| `CMOVcc`, `Jcc`, `SETcc`, `LOOPcc` | **One family page each**, every concrete mnemonic (`CMOVE`, `JNZ`, ...) listed under `aliases` | The 16-30 condition-code variants differ only by the condition. |
| `MOVSB/W/D/Q` (and `CMPS*`, `SCAS*`, `LODS*`, `STOS*`) | **One page per string operation**, width variants as aliases | Width is an operand-size detail. |
| `SHL`/`SHR`/`SAR`, `ROL`/`ROR`/`RCL`/`RCR`, `BT`/`BTS`/`BTR`/`BTC`, `SARX`/`SHLX`/`SHRX` | **Separate pages**, even where the SDM has a single entry | A user searching "rotate through carry" or "arithmetic shift" wants exactly one behaviour. Several pages may cite the same SDM entry. |
| Pure synonyms (`SAL` = `SHL`) | **Alias**, not a page | Same opcode. `/instructions/sal` redirects to `/instructions/shl`. |
| Instructions with a legacy and a 64-bit name (`CBW`/`CWDE`/`CDQE`, `CWD`/`CDQ`/`CQO`) | One page named after the **64-bit** form | Long mode is the point of v1. |

## Open decisions (owner input needed)

These live in `content/roster.yaml` under `deferred`. They are **not** counted in progress.

- `LFENCE`, `MFENCE`, `SFENCE`, `PREFETCHh`, `PREFETCHW`, `CLFLUSH`, `CLFLUSHOPT`, `MOVNTI`:
  ring-3 and memory-based but they are ordering/cache control, not integer arithmetic. Does
  "general-purpose" include them? (People do search "memory barrier".)
- `RDFSBASE`/`RDGSBASE`/`WRFSBASE`/`WRGSBASE`: GPR-only, but usable at ring 3 only if the OS sets `CR4.FSGSBASE`.
- `XGETBV`, `RDPID`: ring-3 feature-detection helpers.

## Not in v1 (possible later phases; nothing is started)

x87 FPU, MMX, SSE/SSE2/SSE3/SSSE3/SSE4, AVX/AVX2/AVX-512, AMX, AES/SHA/GFNI vector forms,
XSAVE-family, segmentation, anything privileged. Do not add them to the roster without an explicit
decision; widening scope changes the product promise ("every instruction you can find here is valid
at ring 3 in 64-bit mode").

## Source of truth and copyright

- Authority: **Intel(R) 64 and IA-32 Architectures Software Developer's Manual, combined volumes**,
  revision recorded in `content/roster.yaml` (`sdm_revision`, currently `325462-093`). Download it as
  described in `README.md`; the PDF is git-ignored and is **not** shipped in the image.
- Page text must be **original summaries**. Do not paste or closely paraphrase SDM prose, and do not
  reproduce its pseudocode. Opcode bytes, mnemonics, operand shapes and flag effects are facts and are fine.
- Any claim that is not in the SDM (compiler behaviour, microarchitecture folklore) must be named in the
  page's `extra_sources`, or left out.

## Glossary

| Term | Meaning |
|---|---|
| mnemonic | Assembler name of an instruction, e.g. `POPCNT`. |
| SDM entry | One instruction reference chapter in SDM Vol. 2, titled like `ADD—Add`. The exact title is the key used in `sdm` fields; find it with `docx86 sdm find`. |
| form | One encodable operand combination, e.g. `ADD r/m64, imm8` with opcode `REX.W + 83 /0 ib`. |
| slug | Lowercase page id and filename stem, e.g. `popcnt`. Appears in URLs. |
| roster | `content/roster.yaml`: the in-scope list. The denominator for progress. |
| CPL | Current privilege level. User space runs at CPL 3, the kernel at CPL 0. |
| REX | Prefix byte (`40h`-`4Fh`) that enables 64-bit operands (`REX.W`) and registers `R8`-`R15`. |
| canonical address | A 64-bit address whose upper bits are a sign extension of bit 47 (bit 56 with 5-level paging). Non-canonical memory operands raise `#GP(0)`. |
