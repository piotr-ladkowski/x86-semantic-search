# Evidence: which sentence of which document supports which claim

Every page says things ("`ZF` is set if the source is 0", "`POPCNT` needs the POPCNT CPU feature"). The
**evidence ledger** records, sentence by sentence, where each of those statements comes from, so a reader (or a
reviewer, or an LLM checking another LLM) can put the page and its sources side by side.

On the site: every page has a *Check each statement against its sources* link in its **Source** box, leading to
`/instructions/<slug>/evidence` (or `/articles/<slug>/evidence`). `/evidence` is the overview.
In the terminal: `docx86 evidence show popcnt`.

## What the reader sees

Each sentence, table row, code listing and structured fact of the page (summary, forms, flags, CPUID
requirement) is a **claim**. Under a claim are the passages it rests on, with the cited sentences highlighted and
the words shared with the claim in bold. A claim is in exactly one state:

| State | Meaning | Counts as "rests on a source" |
|---|---|---|
| `traced` | A person or an LLM read the cited sentence(s) and judged they support the claim, or an exact mechanical match (below) found the very same opcode and syntax in an SDM table row. | yes |
| `derived` | Not stated by a source, but follows from cited sentences. A `note` says how. | yes |
| `run` | A program in the repository (`tests/asm/`) assembles and runs the example, or checks the statement: `make verify-asm` builds them in a Docker toolchain image (NASM, binutils, GCC, MinGW-w64, Wine). `ref` names the file (`run.sh` for tool behaviour such as linker warnings and exit codes). `check` only verifies that the file exists; `make verify-asm` is what runs it. | yes |
| `illustrative` | An invented example. Nothing to quote. | no, by nature |
| `editorial` | Advice, a typical use, terminology. Nothing to quote. | no, by nature |
| `external` | Cited to something that is not one of the indexed documents (a compiler manual, the Optimization Reference Manual). A `note` names it. | no |
| `suggested` | Found by text similarity and **not confirmed by anyone**. A hint. | no, still open |
| `unverified` | Nothing recorded yet. | no, still open |

`rests on a source` = `traced` + `derived` + `run`. `open` = `suggested` + `unverified`. The headline number
deliberately does not count examples and advice, so a page of opinions cannot look "100% checked".

## The design, and why

**The ledger stores pointers, never source text.** Intel's manual, the System V ABI and Microsoft's pages are
copyrighted, and `CLAUDE.md` forbids pasting or closely paraphrasing them. So a ledger entry is
`(document, page or section, fingerprint of the sentence)`. The passage appears on the evidence page only
where the reader has their own copy of the document (the git-ignored files in `docs/`, see README). On a
deployment, which has no such files, the page shows the citations and the coverage, with *"the passage is not
shown on this server"*. Nothing in the repository or the container image contains a sentence of a source.

If the owner decides that short quotes are acceptable (a policy and legal call, not a technical one), the
only change needed is an optional `quote` field on `Support` and rendering it when the document is absent.

**Claims are identified by the fingerprint of their wording.** `textunits.digest` lower-cases, drops everything
but letters and digits and hashes the result (10 hex characters). So evidence survives reformatting
(spacing, punctuation, markdown) but **goes stale, visibly, when the words change**: the old entry no longer
matches any claim, `docx86 evidence check` fails and names it (with the closest current claim), and the page
shows the claim as unchecked again. An edited sentence can never keep vouching for words nobody checked.
After re-reading the sources against the new wording, `docx86 evidence retarget <slug> <old-id> <claim>`
moves the entry over (it does not re-read anything for you).

**Source sentences are identified the same way**, so a pointer is checked against the real document:
`docx86 evidence check` looks every `(document, page, fingerprint)` up and fails if the sentence is gone.
Sentence splitting is in `textunits.split_sentences` and extraction in `sources.py`; changing either changes
fingerprints, so `SPLITTER_VERSION` is stored in each ledger and a mismatch is reported.

**Who made a link is part of the record** (`by`), because a similarity guess and a human reading are not the
same kind of evidence:

| `by` | Made by | Counts as |
|---|---|---|
| `auto` | `docx86 evidence suggest --write`: sentence-embedding cosine + overlap of meaningful words | `suggested` (open) |
| `match` | the same command, when an SDM opcode-table row has the claim's opcode **and** syntax exactly | `traced` |
| `llm` | an LLM read the passage and ran `evidence cite` | `traced` |
| `human` | a person did | `traced` |

A confirmed link replaces the guesses beside it; a guess never overwrites or upgrades a confirmed link.
Ledgers are meant to be mostly `llm` and `human` over time. **A `reviewed` page must have no open claims**
(`check` enforces it).

## Files

```
content/evidence/instructions/<slug>.yaml     one ledger per page; absent = nothing recorded
content/evidence/articles/<slug>.yaml
```

```yaml
splitter: 1
claims:
- id: 62dabf0041                  # fingerprint of the claim's wording (docx86 evidence show lists them)
  gist: Needs the POPCNT CPU feature (reported by CPUID).      # for people reading this file
  support:
  - doc: sdm                      # sdm | sysv | msx64 | msstack | wikibooks
    at: 1695                      # PDF page where the sentence STARTS; for web documents, a section title
    units: [3054813a7d]           # fingerprints of the cited sentences / rows
    part: 64-Bit Mode Exceptions  # display hint; also picks the occurrence when the SDM repeats a sentence
    note: The #UD condition names the CPUID bit.
    # by: llm                     # default; auto | match | llm | human
- id: dd2a389b52
  how: derived                    # source (default) | derived | run | illustrative | editorial | external
  note: The count is a loop over the operand's bits, at most 64.   # required for derived and external
  support: [{doc: sdm, at: 1694, units: [568ba8b630, aec40bb670], part: Description}]
- id: 6cd5f46a02
  how: editorial
  note: Advice.
```

Rules the checker enforces: `how: source` needs `support`; `derived` and `external` need a `note`; `run` needs
`ref` (a file that exists, such as `tests/asm/hello.asm`); `at` is an integer for PDFs and a string for web
documents; every cited unit must exist in the local document (when it is present); every `id` must be a
current claim of the page; no duplicate ids; no ledger for a page that does not exist; a `reviewed` page has
no `suggested` or `unverified` claims. Ledgers are written by the tool in page order; hand edits are fine
(the checker is the safety net) but comments are not preserved.

## Documents

| `doc` | Document | Local copy (git-ignored) | Setting |
|---|---|---|---|
| `sdm` | Intel SDM | `docs/docs.x86.pdf` | `DOCX86_SDM_PDF` |
| `sysv` | System V AMD64 ABI, draft 0.99.6 | `docs/sysv_abi.pdf` | `DOCX86_SYSV_ABI_PDF` |
| `msx64` | Microsoft Learn: x64 calling convention | `docs/ms_x64_calling_convention.html` | `DOCX86_MS_CALLING_CONVENTION_HTML` |
| `msstack` | Microsoft Learn: x64 stack usage | `docs/ms_x64_stack_usage.html` | `DOCX86_MS_STACK_USAGE_HTML` |
| `wikibooks` | Wikibooks x86 Assembly (CC BY-SA) | `docs/wikibooks_x86.html` | `DOCX86_WIKIBOOKS_HTML` |

The download commands are in the README. PDFs need PyMuPDF (the `sdm` dependency group, installed by default
in development, absent from the image). Extracted sentences are cached in `.cache/units/` (safe to delete).

How a PDF becomes units (`sources.PdfSource`): text blocks per page, running headers and footers removed,
SDM headings (*Description*, *Operation*, *Flags Affected*, *… Exceptions*) become the unit's `part`, SDM
opcode tables become one unit per row, a paragraph that continues on the next page belongs to the page
where it starts (that is the page number to cite), hyphenation from line breaks is repaired, `Operation`
pseudocode is one `code` unit. Superscript footnote numbers on 8-bit operands appear as `r/m8[1]`.
Web pages are split by their headings; the first section with a given title wins.

Known limits: PDF layout extraction is heuristic. Figures and some multi-column tables come out as run-on
text; a few sentences are glued to a footnote number; text in images is not extracted. A pointer to such a
unit still works (it is checked against the same extraction), it just reads badly.

## Workflow for an author (human or LLM)

After writing or changing a page (CONTENT_GUIDE step 6 already has you verify against the SDM text):

```bash
uv run docx86 evidence suggest <slug> --write     # exact opcode matches (traced) + similarity guesses (suggested)
uv run docx86 evidence show <slug> --only suggested unverified     # numbered list of what is open
```

Then, for each open claim, in order of how much it matters (flags, forms, faults, CPUID before advice):

1. **Find the sentence.** `uv run docx86 sdm show POPCNT` for the prose; `uv run docx86 evidence find sdm 1694`
   lists the citable sentences of PDF page 1694 with their fingerprints (`--grep text` filters; web
   documents: `evidence find msx64 "Parameter passing"`; `evidence find msx64` lists sections).
   The entry's pages are `docx86 sdm find POPCNT`.
2. **Read it against the claim.** The cited sentence must support what the claim actually says, including its
   numbers, negations and scope ("in 64-bit mode"). If the source says something narrower or different,
   fix the page, do not cite.
3. **Record it.**
   ```bash
   uv run docx86 evidence cite popcnt 16 --doc sdm --at 1695 --unit 3054813a7d --part "64-Bit Mode Exceptions"
   uv run docx86 evidence cite popcnt 10 --doc sdm --at 1694 --grep "number of bits set"      # by text instead of id
   uv run docx86 evidence mark popcnt 22 --as derived --note "ZF is set exactly when the source is zero, so JZ tests 'no bits'."
   uv run docx86 evidence mark popcnt 12 13 --as editorial --note "Typical use."
   ```
   `cite` refuses a sentence that is not in the document, so a typo cannot create a false citation. A claim can
   have several supports (several sentences, several documents). Prefer the 64-bit-mode occurrence when the
   SDM repeats a sentence per mode.
4. **`derived` is for reasoning, not for convenience.** Use it when the claim needs a step the sources do not
   state (a range from a loop bound, "no imm64 form" from a table that lists none). If a sentence says it
   outright, it is `traced`. If nothing in any source says or implies it, it is `editorial`, `external`, or
   it should be cut.
5. **Check.** `make evidence` (= `docx86 evidence check`). It must pass.

Never set `by: human` unless a person did read it. Never leave guesses and call the page finished: say how
many claims are open in your report.

## Commands

```
docx86 evidence status [slug]          coverage of every page, or the claims of one (numbered)
docx86 evidence show <slug> [--only STATE ...]    claims with the passages they cite (needs the documents for text)
docx86 evidence find <doc> [page|section] [--grep T] [--full]   citable sentences with fingerprints
docx86 evidence cite <slug> <claim> --doc D --at P (--unit ID,.. | --grep T) [--part X] [--by llm|human] [--note N]
docx86 evidence mark <slug> <claim>... --as derived|run|illustrative|editorial|external [--note N] [--ref F]
docx86 evidence retarget <slug> <stale-id> <claim>     carry a reworded claim's evidence onto its new text
docx86 evidence prune [slug]           drop the evidence of claims that no longer exist
docx86 evidence suggest <slug> [--scope doc:pages ...] [--also ...] [--top N] [--write [--min 0.6]]
docx86 evidence suggest --all --write  every instruction page, SDM pages taken from its sdm_entries
docx86 evidence check [--no-sources]   validate every ledger; part of `make check`. --no-sources is the content-only check
                                       the image build runs: it neither opens documents nor tests that `run` files exist
```

`<claim>` is the number shown by `status`/`show`, a claim id, or an id prefix. `--scope` takes
`sdm:1693-1695`, `sysv:16-18`, `msx64:*` (all sections) or `wikibooks:Section title`; articles have no default
scope. `suggest` uses the configured embedder (`fastembed` by default; the offline hash embedder works but ranks
lexically only).

## Site and API

| Route | |
|---|---|
| `GET /evidence` | Overview: every page's coverage, the states explained. |
| `GET /instructions/{name}/evidence`, `/articles/{slug}/evidence` | The claims of a page with their sources. `?state=traced` (any state name) filters. Aliases redirect like the page. |
| `GET /api/evidence` | JSON totals and per-page counts. |
| `GET /api/evidence/{instructions\|articles}/{slug}` | JSON: every claim with state, `how`, `note`, supports and `where`; includes the cited passage text **only** on a machine that has the document. |

The pages need no JavaScript. They are read-only; nothing a visitor does changes a ledger.

## Reviewing a page (the human step)

Open `/instructions/<slug>/evidence` locally. For each *traced* and *derived* claim, read the highlighted
sentence next to the claim. That is the review: it replaces re-reading 3-6 SDM pages. Look for claims that say
more than their source (a number, "always", a mode), then set `status: reviewed` in the page only when
`docx86 evidence check` passes and nothing is open. Suggestions you disagree with: replace them with `cite`.
