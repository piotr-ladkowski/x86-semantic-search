# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**doc/x86** (spelled `docx86` in code, CLI, image, Kubernetes names and `DOCX86_*` env vars; use `doc/x86`
only for user-facing text). A FastAPI web app for semantic search over x86-64 instruction documentation: a user describes what
they want in plain English and gets the matching instruction's page (forms, flags, gotchas, example).
**v1 scope: x86-64 long mode, user-space, scalar integer / general-purpose instructions.** Most of the
work in this repo is *writing instruction pages* (`content/`), largely by LLMs, verified against the Intel SDM.

Read before working: `docs/SCOPE.md` (what is in scope and the rule for deciding),
`docs/CONTENT_GUIDE.md` (how to write a page, step by step), `docs/ARCHITECTURE.md` (search, config, k8s).

## Commands

```bash
make setup      # uv sync + npm ci
make dev        # Tailwind build, then uvicorn --reload on :8000 (rebuilds a stale index on start)
make check      # ruff + pytest + content validation + progress freshness -> run before finishing
make test       # pytest (hash embedder; no model/network)
uv run pytest tests/test_search.py::test_semantic_ranking   # a single test
make validate   # uv run docx86 validate   (add --sdm to check roster titles against the PDF)
make progress   # regenerate README progress block + content/README.md (never hand-edit them)
make evidence   # uv run docx86 evidence check: stale claims, bad pointers, reviewed pages fully covered
make verify-asm # assemble + run the articles' example programs in Docker (tests/asm; Windows ones under Wine)
make index      # embed content/ -> index/   (needed when search-relevant text changed)
make eval       # real-model search regression check (content/eval.yaml); downloads the model once
make fmt        # ruff fix + format
make image IMAGE=... TAG=...    # docker build; manifests in deploy/k8s (kustomize)
```

On NixOS, `uv run`/`make` may fail with `ImportError: libstdc++.so.6` (numpy's extension can't find it):
`export LD_LIBRARY_PATH=$NIX_LD_LIBRARY_PATH` first. Details in README.md under Development.

Wikibooks lookup (needs `docs/wikibooks_x86.html`, a secondary source for assemblers, OS and ABI topics only):
`uv run docx86 wiki find|show|grep <text>`. Never copy its prose (CC BY-SA); cite the section in `extra_sources`.

Evidence ledger (`docs/EVIDENCE.md`): which sentence of which document supports which statement of a page.
`uv run docx86 evidence status|show|find|cite|mark|suggest|check`. After writing or editing a page run
`evidence suggest <slug> --write`, then read the open claims against the documents and `cite`/`mark` them.

SDM lookup (needs `docs/docs.x86.pdf`; download command is in README.md):
`uv run docx86 sdm find <text>` lists matching entries with PDF pages;
`uv run docx86 sdm show <MNEMONIC>` prints that entry's pages as text.

## Architecture in brief

`content/*.md` + `roster.yaml` -> `content.py` (validate) -> `index.py` (several embedded "search units" per
page: a summary plus one per `search_phrases` entry) -> `index/` (npy + json) -> `search.py` (cosine over all
units, best unit per page, exact-mnemonic pin, small token boost) -> `web.py` (Jinja2 + Tailwind, no JS) and
`api.py` (`/api/*`). Embeddings come from `fastembed` (ONNX, `bge-small-en-v1.5`); there is no database.
The index is built **at Docker build time** and baked into the image with the model, so pods are stateless
and offline. A stale index makes the app refuse to start (production) unless `DOCX86_REBUILD_STALE_INDEX=1`.

The schema in `src/docx86/models.py` is the content contract; `tests/test_docs.py` fails if
`docs/CONTENT_GUIDE.md` drifts from it. Settings are `DOCX86_*` env vars (`config.py`, table in ARCHITECTURE.md).

## Rules that are easy to get wrong

- **Roster gates content.** A page may exist only for a slug in `content/roster.yaml` -> `instructions`.
  Don't add to `instructions`, `deferred` or `excluded` on your own initiative; scope is the owner's call.
- **Verify against the SDM, never from memory.** Every page's flags, forms, operand-size behaviour and CPUID
  requirement must be checked against the SDM text via `docx86 sdm show`. Anything not in the SDM goes in
  `extra_sources` or is cut.
- **Never paste or closely paraphrase SDM prose or pseudocode into a page** (copyright). Write original summaries.
  (The one exception is the short attributed quotation in the evidence ledger, below.)
- **Code in articles must be tested.** Any `nasm` listing of 5+ lines in an article has to exist in `tests/asm/` (run
  `make verify-asm`); `make test` enforces it. Conventions and tooling claims need a primary source or a real run, not
  just Wikibooks. State what was *not* run (for example real Windows).
- **Label code fences** (```` ```nasm ````, ```` ```bash ````): they are highlighted on the server by `highlight.py`; colours are rules in `assets/app.css` (run `make css`), and a test fails if content uses a token class that has no rule.
- **Authors write `status: draft`.** Only a human sets `reviewed`.
- **Editing a sentence orphans its evidence.** Evidence is keyed by the fingerprint of a claim's wording, so
  `make evidence` fails after you reword a checked sentence. Re-read the source, then fix the ledger (`cite`
  again, or change the `id`). Never write `by: human`; record what you actually read as `llm`, and leave a
  claim open rather than citing a sentence that does not say it.
- **The evidence ledger may quote the cited sentence, and only that** (owner decision 2026-10-03, right of
  quotation): one sentence or table row, at most 400 characters, with its document and page, never *Operation*
  pseudocode or long tables. `docx86 evidence cite` and `evidence quote` add quotes from the local document and
  `check` verifies them. Do not paste source prose into `note`, the page text or anywhere else, and do not quote
  the neighbouring sentences: the surroundings are rendered from the reader's own copy in `docs/`.
- **Generated files:** `content/README.md`, the block between `<!-- progress:start/end -->` in `README.md`,
  `index/`, `src/docx86/static/app.css`. Regenerate with `make progress` / `make index` / `make css`.
  After adding or changing a page, run `make progress` (the test suite fails on stale progress files).
- **Don't deploy `DOCX86_EMBEDDER=hash`.** It is a lexical stand-in for tests; production uses `fastembed`.
- **Changing the embedding model or `search_phrases`/summary text requires a new index** (`make index`).
- Handlers in `web.py`/`api.py` are plain `def` on purpose (embedding is CPU work; FastAPI runs them in a threadpool).
- `docs/docs.x86.pdf` is git-ignored and excluded from the Docker context. Do not commit it or copy it into the image.
- **Tracing (OpenTelemetry) is configured only through `OTEL_*` env vars** and is off without an exporter (`telemetry.py`,
  section *Observability* in ARCHITECTURE.md). Use FastAPI's built-in telemetry, not `opentelemetry-instrumentation-fastapi`;
  keep `auto_configure`, `metrics` and `logs` off in `telemetry.fastapi_config` (they would export metrics/logs and leak user input).
  Never put the user's query text on a span without going through `DOCX86_TRACE_USER_DATA`; custom attributes are namespaced `docx86.*`.
