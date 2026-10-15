# Roadmap: development directions, ranked

A ranked TODO list for what to build next. It was produced from a survey of the repository on 2026-10-08
and should be re-ranked whenever a block below is finished. Scope questions still belong in
[SCOPE.md](SCOPE.md); this file is about *what to do next*, not what is in scope.

Tick a box when the item is done and add the date. Delete an item that turns out to be wrong rather
than leaving it unticked forever.

## Where the repo stood on 2026-10-08

The tooling is far ahead of the content: validated schema, evidence ledger with fingerprinted claims and
quotes, a Docker toolchain that runs the article examples, tracing, a hardened Kubernetes deployment. The
product promise ("describe what you want and get the instruction") is the thin part.

| Measure | Value |
|---|---|
| Instruction pages | 32 of 102, none `reviewed` |
| Articles | 11 |
| Evidence claims | 1332, 0 open, 0 checked by a human (every ledger entry is `by: llm` or `match`) |
| Search eval (`content/eval.yaml`) | 55 queries; the pass bar is top-3 |
| CI (`.github/workflows/ci.yaml`) | builds and pushes the image only; `make check`, `make eval`, `make verify-asm` do not run |

## 1. Finish the v1 roster, in demand order

With 31% coverage, common queries land on wrong pages because the right page does not exist. This is the
biggest lever on product value and the authoring pipeline for it already exists (CONTENT_GUIDE.md).

Write first the pages users hit first:

- [ ] Control transfer: `call`, `ret`, `jmp` (then `int`, `enter`, `leave`)
- [ ] Conditionals: `setcc`, `cmovcc`
- [ ] Atomics: `lock`, `xadd`, `cmpxchg`, `cmpxchg16b`
- [ ] Bit ops: `bt`, `bts`, `btr`, `btc`, `bsf`, `bsr`, `lzcnt`, `tzcnt`
- [ ] Multi-precision arithmetic: `adc`, `sbb`, `adcx`, `adox`, `mulx`
- [ ] System-ish: `syscall`, `cpuid`, `rdtsc`, `rdtscp`, `pause`
- [ ] Flag control: all nine (`stc` ... `popf`) in one batch; they are tiny
- [ ] Rotates and double shifts: `rol`, `ror`, `rcl`, `rcr`, `shld`, `shrd`
- [ ] Remaining data transfer: `bswap`, `cdqe`, `cqo`
- [ ] Remaining string: `cmps`, `scas`, `lods`
- [ ] Rest of BMI1/BMI2, `crc32`, `movbe`, `rdrand`, `rdseed`, `ud2`, `xlat`, `nop` relatives, `endbr64`

Run `make eval` after every batch: a new page can steal queries from older ones (CONTENT_GUIDE.md,
"Writing `search_phrases`").

## 2. Make search honest about gaps

Typing `call` today returns unrelated semantic matches because CALL is in the roster but unwritten. All of
these are small changes to `src/docx86/search.py`, `web.py` and the templates.

- [x] (2026-10-08) When the query resolves to a roster slug that has no page, say "planned, not written yet"
      (and which category it is in) instead of showing weak semantic results. Done as `Content.resolve_roster`:
      also answers `deferred` and `excluded` names with the roster's reason, and family names (`sete`, `cmovne`,
      `scasb`, `repne`) resolve while their pages do not exist. `/instructions/{name}` 404s say the same.
      Not covered: aliases that live only in roster `note` text (`CBW`, `CDQ`, `MOVSXD`, `INT3`, `PUSHFQ`, ...);
      a structured `aliases` field on roster entries would close that, owner's call.
- [x] (2026-10-08) Render the matched phrase next to each result ("Matched 'count the set bits'", "Exact
      mnemonic match", "Matched the page summary"); also in `/api/search` as `via` / `via_kind`.
- [x] (2026-10-08) Relevance floor, measured: `DOCX86_SEARCH_FLOOR=0.64`, weak results labelled and dimmed,
      "No good match" when nothing clears it, five off-topic `negatives` in `content/eval.yaml`. Finding: the
      floor only catches clearly off-topic queries; x86 queries that are out of scope (floats, SIMD, MSRs) score
      0.71-0.88, above many genuine hits, so `scope.py` adds a word-based out-of-scope notice instead
      (`xmm0`, `avx`, `float`, `cr3`, ...). Details in ARCHITECTURE.md, "Search algorithm".
- [x] (2026-10-08) Tighten the eval: per-query `top: 1` bars (36 of 53 queries), `negatives` against the floor,
      and `make eval` prints each query's lead, the weakest expected page and the strongest negative.
      Baseline: hit@1 42/53, hit@3 53/53, negatives rejected 5/5, margin 0.649 vs 0.619.

## 3. Turn the evidence ledger into actual review

All 1332 claims are closed, but every one was closed by an LLM and no page is `reviewed`, so the draft
banner on every page is still literally true. The ledger was built to make review fast; use it.

- [ ] Second-reader pass: a command that re-reads each `traced` claim against its stored quote and flags
      pairs where the quote does not entail the claim (wrong number, wrong mode, "always" vs "if"). The
      quotes are in the repository, so this needs no PDF and can run in CI with a *different* model than
      the author. Output: a list of claim ids to re-check, never an automatic state change.
- [ ] Review queue for a human: sample N `traced`/`derived` claims across pages, show claim and quote side by
      side, accept or reject each in a minute. Rejections reopen the claim (`unverified`) with a note.
- [ ] Get the first ten pages to `status: reviewed` (EVIDENCE.md, "Reviewing a page"), starting with the
      pages search returns most often (`mov`, `add`, `cmp`, `jcc`, `lea`, `xor`, `test`, `push`, `pop`, `imul`).

## 4. Gate the image on the checks

`ci.yaml` pushes `:latest` on every push to `main` without running lint, tests, progress freshness or eval.
The Docker build does run `validate`, `evidence check --no-sources` and `build-index`, so content errors are
caught, but a failing test or a stale progress file is not.

- [ ] Run `make check` in CI before the image build; fail the push on red.
- [ ] Cache the embedding model in CI and run `make eval`.
- [ ] Run `make verify-asm` when `content/articles/**` or `tests/asm/**` change (Docker is available on
      the GitHub runner).
- [ ] Windows runner job: `nasm` and MSVC `link.exe` are on `windows-latest`. Assemble and run
      `tests/asm/hello_win.asm` and `hello_win32.asm` there, then remove the "not run on real Windows"
      caveat from `content/articles/nasm-windows.md` and cite the run as `run` evidence.

## 5. Serve agents directly

`/api/*` is described as being for tools and agents, and the docs are written for LLM readers, yet an
agent has no tool surface and no markdown.

- [ ] MCP server (stdio and HTTP) exposing `search`, `get_instruction`, `list_instructions`, `get_evidence`
      as tools. Thin wrapper over the in-process engine; ship it as `docx86 mcp` in the same image.
- [ ] Markdown for pages: `Accept: text/markdown` or `/instructions/{slug}.md` returning the source page
      (front matter plus body), so editors and agents can read a page without scraping HTML.
- [ ] `/llms.txt` listing the pages, the articles and the API.

## 6. Accept disassembly as input

SCOPE.md names "reading compiler output" as a core use, but a pasted objdump or GDB line such as
`movl %eax, %edx` or `mov eax, DWORD PTR [rbp-4]` resolves nothing today.

- [ ] AT&T mnemonics in the resolver: strip the `b/w/l/q` suffix and map `movslq`, `cltq`, `cqto` and the
      other renamed forms to their pages.
- [ ] Parse a pasted Intel or AT&T line (optionally with a leading address and bytes) down to its mnemonic
      and pin that page; keep the semantic search as a fallback.
- [ ] A "what compilers emit this for" section on pages where it helps (`lea`, `imul`, `cmovcc`, `setcc`,
      `xor`, `test`, `sar`), with the C snippet and the GCC output produced inside the `tests/asm` toolchain
      and recorded as `run` evidence. Compiler claims need a real run (CONTENT_GUIDE.md).

## 7. Decide the deferred instructions

Owner decision; see SCOPE.md "Open decisions" and `content/roster.yaml` -> `deferred`.

- [ ] `LFENCE`, `MFENCE`, `SFENCE`, `PREFETCHh`, `PREFETCHW`, `CLFLUSH`, `CLFLUSHOPT`, `MOVNTI`:
      "memory barrier" is a query people type and the current answer is nothing. Suggestion: include them
      as a new category "Memory ordering & cache", which keeps the ring-3 promise.
- [ ] `RDFSBASE`/`RDGSBASE`/`WRFSBASE`/`WRGSBASE`: suggestion: keep deferred (OS-gated).
- [ ] `XGETBV`, `RDPID`: suggestion: include; both are ring-3 feature queries next to `CPUID`.

## 8. Small web polish

- [ ] Content is immutable per image: send `Cache-Control` with a long max-age and an `ETag` derived from
      the image/content hash on pages and static files; gzip responses.
- [ ] `robots.txt`, `sitemap.xml` and OpenGraph/Twitter meta tags on page and article templates.
- [ ] CORS for `/api/*` (and the `traceparent` headers, see ARCHITECTURE.md "Browser frontend") if a
      browser client is ever built.
- [ ] Show `related` slugs that have no page yet as "planned" instead of hiding them, so a reader knows the
      page is coming rather than missing.

## 9. Later

- The evidence ledger (fingerprinted claims, quote-only provenance, states, `suggest`) is general enough to
  extract as a standalone tool for any LLM-written documentation. Worth doing only after v1 is reviewed.
- Widening scope to SSE/AVX changes the product promise and is explicitly not started (SCOPE.md,
  "Not in v1"). Do not begin before v1 is complete and reviewed.

## Suggested order

Do blocks 2 and 4 first: both are small and they protect trust in what is already published. Then grind
through block 1 with block 3 running alongside, so reviewed pages accumulate as drafts do. Blocks 5 and 6
are the most interesting new capability and make sense once coverage passes about two thirds of the roster.
