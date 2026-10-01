# Content guide: writing instruction pages and articles

This is the working procedure for adding or reviewing content. It is written so an LLM agent can follow
it step by step; a human can too. Scope questions ("is this instruction in v1?") are answered in
[SCOPE.md](SCOPE.md), not here.

**The contract:** every file under `content/` is validated by `uv run docx86 validate` (schema in
`src/docx86/models.py`). If validation passes and the checklist below is satisfied, the page is
done. Never hand-edit generated files (`content/README.md`, the progress block in `README.md`).

## Where things live

| Path | What | Edited by |
|---|---|---|
| `content/roster.yaml` | The in-scope instruction list (`instructions`), plus `deferred` and `excluded`. | Owner / scope decisions only |
| `content/instructions/<slug>.md` | One page per instruction. Front matter + four fixed sections. | Authors |
| `content/articles/<slug>.md` | Rare short explainers spanning several instructions. | Authors |
| `content/eval.yaml` | Search regression queries (`query` -> `expect` slug). | Authors |
| `content/README.md`, progress block in `README.md` | Generated checklist. | `make progress` only |
| `docs/docs.x86.pdf` | The Intel SDM (git-ignored, local only). | - |

## Procedure: add one instruction page

1. **Pick the instruction.** Take the next `todo` row in `content/README.md`, or the slug you were given.
   It must exist in `content/roster.yaml` -> `instructions`. If it does not, stop and read SCOPE.md; do not
   add it yourself unless the task says to.
2. **Read the SDM entry.** The roster entry's `sdm` field holds the exact entry title(s).
   ```bash
   uv run docx86 sdm show POPCNT            # prints the entry's PDF pages as text (default max 6 pages)
   uv run docx86 sdm show POPCNT --max-pages 12
   uv run docx86 sdm find shift             # list entries whose mnemonic/title matches
   ```
   Read **all** of it: the opcode table, the description, *Flags Affected*, and the *64-Bit Mode Exceptions*
   section. The PDF text puts each table cell on its own line; read columns in order
   (opcode, instruction, op/en, 64-bit mode, compat mode, description). Page numbers are 1-based PDF indexes.
   If several entries share a mnemonic, `show` takes the first and prints the others to stderr.
3. **Create `content/instructions/<slug>.md`** from the template at the bottom of this file. The filename
   must equal the `slug` field.
4. **Fill the front matter** using the field reference below. Copy `mnemonic`, `category` and
   `sdm_entries` from the roster entry exactly; validation checks they match.
5. **Write the four body sections** using the style rules below.
6. **Verify every factual claim against the SDM text you just read** (flags, operand sizes, which forms are
   valid in 64-bit mode, CPUID requirement, faults). Do not write from memory. If a claim is not in the SDM,
   either cut it or cite where it comes from in `extra_sources`.
7. **Add 2-3 lines to `content/eval.yaml`** with queries phrased as a user would, not copied from your
   `search_phrases`. For an article add `kind: article` to the line and `expect` the article's slug.
8. **Run the gate:**
   ```bash
   make validate    # schema, cross-references, roster consistency
   make progress    # regenerate the checklist/progress files (commit them with the page)
   make test        # includes "progress files are current"
   make eval        # optional but recommended: real-model search check (downloads the model once)
   ```
9. **Report** what you added and anything you were unsure about. Set `status: draft`. Never set
   `status: reviewed`; that means a human compared the page to the SDM.

### Definition of done

- [ ] `make validate` and `make test` pass; `make progress` was run.
- [ ] Every `forms` entry is valid in 64-bit mode in the SDM table, with the opcode copied from the SDM.
- [ ] `flags` matches *Flags Affected* (including conditions, e.g. "unchanged when count is 0", in `note`).
- [ ] `cpuid_feature` is set iff the instruction is not baseline x86-64.
- [ ] The 64-bit-mode specifics are covered where relevant: default operand size 32 bits, REX.W, 32-bit
      results zero-extend into the 64-bit register, 8/16-bit results do not, RIP-relative addressing.
- [ ] No sentence is copied or closely paraphrased from the SDM; no SDM pseudocode.
- [ ] Gotchas are things that cause real bugs, not restatements of the description.
- [ ] The example assembles as written in NASM syntax (Intel operand order) and its comments are true.
- [ ] `search_phrases` follow the rules below; eval lines added.

## Front matter reference (instruction pages)

| Field | Required | Rule |
|---|---|---|
| `slug` | yes | Lowercase `[a-z0-9-]`; equals the filename stem and the roster slug. |
| `mnemonic` | yes | Uppercase primary mnemonic. For families use the roster's name (`CMOVCC`, `JCC`, `SETCC`). |
| `aliases` | yes (may be `[]`) | Other uppercase mnemonics that should land here (`SAL`, `CMOVE`, `JNZ`). Must not collide with any other page's slug, mnemonic or alias. |
| `title` | yes | Short human name: `Add`, `Population Count`. |
| `summary` | yes | One sentence, <= 160 chars, shown in search results and used for search. Say what it does, not what it is. |
| `category` | yes | One of the `Category` values (matches roster). |
| `status` | no (default `draft`) | `draft` or `reviewed`. Authors write `draft`. |
| `cpuid_feature` | no | e.g. `POPCNT`, `BMI2`, `ADX`; `null` or omitted for baseline x86-64. |
| `sdm_entries` | yes | List of exact SDM Vol. 2 outline titles; identical to the roster entry's `sdm`. |
| `extra_sources` | no | One free-text citation per claim that is not in the SDM. |
| `flags` | no | `modified` / `undefined` / `read` lists of `CF PF AF ZF SF DF OF`, plus `note`. Omit all for "no flags affected" and say so in `note`. A flag listed nowhere is unaffected. |
| `forms` | yes (>= 1) | 64-bit-mode-valid forms only: `syntax` (Intel syntax, SDM spelling), `opcode` (SDM opcode column), optional `note`. If the 8/16/32-bit forms are the same shape as the listed 64-bit ones, say so in the first form's `note` instead of listing all of them. Keep to about 8 or fewer. |
| `search_phrases` | yes (>= 3) | See below. |
| `related` | no | Slugs that appear in the roster (they need not be written yet; the UI links only those that exist). |

Unknown fields are rejected.

## Body sections

The body is Markdown with **exactly these H2 headings, in this order** (validation requires all four to be
present and non-empty; do not add an H1, the title comes from front matter):

| Heading | Content |
|---|---|
| `## What it does` | 2-4 sentences. The operation in plain words, which operands are read/written, what the key flags mean. |
| `## When to use it` | Bullets of the situations that lead someone here, including "use X instead" pointers. |
| `## Gotchas` | Bullets, most bug-prone first: operand-size and zero-extension rules, immediate sign-extension, flag surprises, faults a user can hit at ring 3 (`#UD`, `#GP(0)` for non-canonical addresses, `#DE`), `LOCK` rules, required CPUID feature, alignment, REX/high-byte limits. |
| `## Example` | At least one fenced ```` ```nasm ```` block, NASM/Intel syntax, with comments that state results. Prefer 3-8 lines. |

Style rules:

- Write for a competent programmer who does not know this instruction. Be concrete: name registers and values.
- Use backticks for mnemonics, registers and flags in running text. Lowercase mnemonics in code, uppercase in prose headings.
- Do not use raw HTML (it is escaped). Tables and lists are fine.
- **Label every code fence** so it is coloured: ```` ```nasm ```` for x86 assembly (Intel syntax; `asm` is treated as the same), ```` ```bash ```` for shell commands, ```` ```bat ```` for Windows command lines. An unlabelled fence stays plain, which suits program output.
- Keep it small: the whole body should fit on one screen or two. If a page needs more, it is probably two instructions.
- Do not put a "See also" section in the body; use `related`.

## Writing `search_phrases`

These are the queries the instruction should be the answer to; each becomes its own search vector, so
they are the biggest lever on search quality.

- 3-8 phrases, 2-10 words each, in the voice of someone who does **not** know the mnemonic:
  `count the number of set bits`, not `POPCNT instruction`.
- Cover distinct intents and the common synonyms or other names (`population count`, `hamming weight`).
- Be specific. A phrase that fits several instructions (`multiply`, `compare two values`) pulls the wrong
  page; say what is different (`multiply and keep the full 128-bit result`).
- **Avoid generic filler and bare digits.** The embedding model treats the *shape* of a short sentence as much as its
  content, so a phrase like "put a 64-bit number in a register" or "multiply a register by 3, 5 or 9" attracts every query
  shaped like "... a register" or containing a digit, whatever they are about. Measured when the first 16 pages were
  written: such phrases pulled "turn on bit 5 in a register" to MOV and "turn 5 into -5" to LEA. Lead with the verb and
  noun that are specific to the instruction ("multiply by 3, 5 or 9 in one instruction", "count a loop down to zero").
- **Cover the instruction's most common job explicitly.** OR initially had phrases for masks and flags but none for the
  commonest request, setting a single bit, so it lost that query to unrelated pages.
- **Re-run `make eval` after adding a page.** A new page can steal queries from older ones; if `hit@1` drops, rewrite the
  new page's phrases (not the old ones) first. To compare candidate phrases, embed them and look at their similarity to the
  queries they should and should not win; do not tune against the eval until it passes by memorising it.
- Never include the mnemonic alone: exact mnemonic and alias lookups are handled separately and win automatically.
- Do not copy phrases into `content/eval.yaml`: that file must test *unseen* wording.

## Articles

Write an article only for an idea that spans several instructions and does not fit in one page (for
example "why writing EAX clears the top half of RAX"). Fields: `slug`, `title`, `summary` (<= 200 chars),
`tags`, `status`, `related_instructions` (roster slugs), `sdm_refs` (volume/section/PDF pages you verified
against), `extra_sources`, `search_phrases`. The body is free-form Markdown with no H1; `##` headings are
fine. The same accuracy and no-copying rules apply. Articles never count toward instruction progress.

### Articles about tools, operating systems and ABIs

Topics such as assemblers, linking, calling conventions and register roles are outside the SDM, so the usual
"verify against the SDM" step is replaced by a stricter one. Everything in such an article must come from one of:

1. **The SDM**, for what a register or instruction does (list the entries in `sdm_refs`).
2. **A primary document**, for conventions: the System V AMD64 ABI, Microsoft's x64 documentation. Cite the section
   in `extra_sources`.
3. **Running a real toolchain.** Every command and every listing of five or more lines must have been executed.
4. **The Wikibooks book** (`uv run docx86 wiki find|show|grep`) only as a *map*: it is largely 32-bit and informal.
   Cite the section in `extra_sources`, never copy its prose (CC BY-SA), and re-check anything 64-bit.

Rules for code in articles:

- **Put each long listing in `tests/asm/` and run `make verify-asm`.** The runner (Docker: NASM, GCC, MinGW-w64, Wine)
  assembles, links and runs every program there and compares the output with `expected_*.txt`. Windows programs run
  under Wine, so say plainly in the article that they were not run on real Windows.
- `tests/test_asm_examples.py` (part of `make test`) fails if an article contains a `nasm` listing of five or more
  code lines that is not present in `tests/asm/`. Comments may differ; code may not.
- Commands you could not run (for example `link.exe`) must be labelled as not run in the article itself.
- State tool versions that were tested in `extra_sources`.

## Reviewing a page (for humans)

Open the SDM entry (`uv run docx86 sdm show <MNEMONIC>`), check each field and each claim against it,
fix what is wrong, then change `status` to `reviewed` and run `make progress`.

## Common `validate` errors

| Message | Fix |
|---|---|
| `not in content/roster.yaml ...` | The instruction is out of scope or not yet in the roster. See SCOPE.md. |
| `mnemonic/category differ from roster entry` / `sdm_entries differ` | Copy the values from the roster entry exactly. |
| `missing or empty required section '## X'` | Add the section; heading text must match exactly. |
| `'## Example' must contain a fenced code block` | Use a ```` ``` ```` fence. |
| `body must not contain an H1` | Remove the `# Title` line. |
| `... collides with ...` | An alias or mnemonic is already used by another page. |
| `related 'x' is not a slug in content/roster.yaml` | Use a roster slug. |
| `SDM entry not found` (`validate --sdm`) | The title must match the PDF outline exactly (note `ADOX — ...` has spaces around the dash); use `docx86 sdm find`. |

## Template

````markdown
---
slug: example
mnemonic: EXAMPLE
aliases: []
title: Human Readable Name
summary: One sentence, at most 160 characters, saying what it does.
category: binary-arithmetic   # copy from roster
status: draft
cpuid_feature: null           # or e.g. POPCNT
sdm_entries: ["EXAMPLE—Title Exactly As In The Roster"]
extra_sources: []
flags:
  modified: [OF, SF, ZF, AF, CF, PF]
  undefined: []
  read: []
  note: "What the lists cannot say."
forms:
  - {syntax: "EXAMPLE r/m64, r64", opcode: "REX.W + 01 /r", note: "Optional."}
search_phrases:
  - how someone would ask for this
  - another way to ask
  - a third distinct intent
related: [other-slug]
---

## What it does

...

## When to use it

- ...

## Gotchas

- ...

## Example

```nasm
example rax, rbx    ; rax = ...
```
````

See `content/instructions/add.md` and `content/instructions/popcnt.md` for finished examples.
