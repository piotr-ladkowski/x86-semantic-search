# Architecture

## Data flow

```
content/instructions/*.md ─┐
content/articles/*.md      ├─ load_content() ── validate (schema, xrefs, roster) ──┐
content/roster.yaml ───────┘                                                       │
                                                                                   ▼
                              build_units(): per page 1 summary unit + 1 unit per `search_phrases`
                                                                                   │
                                   embedder.embed_documents()  (fastembed, ONNX, 384-d, L2-normalised)
                                                                                   ▼
                          index/{units.json, vectors.npy, meta.json}   <- `docx86 build-index`
                                                                                   │  baked into the image at build time
                                                                                   ▼
 request ─► SearchEngine.search(): embed query ─► dot product with all vectors ─► best unit per page
            + exact mnemonic/alias pin, + small token boost ─► ranked Hits ─► HTML (Jinja2) or JSON
```

Everything is read-only at runtime. There is no database, no vector store service, no writable volume and
no outbound network access. The corpus is small (hundreds of pages -> thousands of vectors), so
brute-force cosine similarity over an in-memory `numpy` matrix is exact and takes about 1 ms.

## Modules (`src/docx86/`)

| Module | Responsibility |
|---|---|
| `models.py` | Pydantic schema for pages, articles and the roster. **The schema is the content contract**; `docs/CONTENT_GUIDE.md` describes it and a test keeps the two in sync. |
| `content.py` | Parse front matter + Markdown, split `##` sections, render HTML (raw HTML in Markdown is escaped), run cross-reference checks, report *all* problems at once. |
| `embedding.py` | `Embedder` protocol with `FastEmbedEmbedder` (production) and `HashEmbedder` (tests/offline dev only, lexical, never deploy). |
| `index.py` | Build, save, load the index; `ensure_fresh()` detects a stale index (content or embedder changed). |
| `search.py` | Query-time ranking (see below). |
| `main.py` | App factory, lifespan (loads the engine once), `/healthz`, `/readyz`, 404 handling. |
| `web.py` / `api.py` | HTML routes / JSON routes under `/api`. Handlers are sync `def`, so FastAPI runs them in its threadpool and embedding does not block the event loop. |
| `progress.py` | Generates the README progress block and `content/README.md` from roster + pages. |
| `sdm.py` | Authoring aid: maps instruction mnemonics to page ranges of the local SDM PDF using its bookmark outline. Not imported by the web app. |
| `highlight.py` | Server-side syntax highlighting of fenced code blocks with Pygments (no JavaScript). Corrects the NASM lexer for prefixes (`rep movsb`) and directives (`equ`); the colours are CSS rules in `assets/app.css`, and `tests/test_highlight.py` fails if content produces a token class with no rule. |
| `wikibooks.py` | Authoring aid like `sdm.py`: parses the Wikibooks book into sections so authors can look up assembler, OS and ABI topics (`docx86 wiki ...`). stdlib only; not imported by the web app. |
| `telemetry.py` | OpenTelemetry tracing: builds the tracer provider from `OTEL_*` env, scrubs user data from spans, and returns the `telemetry=` config for FastAPI. See *Observability*. |
| `textunits.py`, `claims.py`, `sources.py` | Evidence plumbing: sentence splitting and fingerprints; breaking a page into claims; reading the reference documents (SDM, System V ABI, Microsoft pages, Wikibooks) into citable units. Authoring/review only; PyMuPDF is imported lazily and is not in the image. |
| `evidence.py`, `suggest.py`, `evidence_cli.py` | The evidence ledger (pointers from claims to source sentences, coverage, checking, passage views), the candidate finder behind `evidence suggest`, and the `docx86 evidence ...` commands. See `docs/EVIDENCE.md`. |
| `cli.py` | `docx86 validate | build-index | progress | eval | sdm | wiki | evidence`. |
| `templates/`, `static/` | Jinja2 templates; Tailwind output `static/app.css` (built, git-ignored). |

## Search algorithm

1. Each page contributes **several search units**: one summary unit (mnemonics + title + summary + "What it
   does" + "When to use it") and one unit per `search_phrases` entry. A short user query matches a short
   phrase far better than a long paragraph. Articles work the same way.
2. The query is embedded and compared against every unit; each page's score is its **best unit**. Query vectors are cached in an in-process LRU (512 entries): the HTML results page searches twice per request (instructions, then articles) and popular queries repeat.
3. **Exact mnemonic.** If the whole query equals a slug, mnemonic or alias (case-insensitive), that page is
   pinned first with score 1.0 (`popcnt`, `SAL`).
4. **Token boost.** If a mnemonic/alias appears as a token inside a longer query, that page gets
   `+0.08` (`what does lea do`). The boost is deliberately small because `AND`, `OR`, `NOT`, `CALL`,
   `TEST`, `LOOP` are also ordinary English words.
5. Results are sorted by score. `kind=instruction|article` filters; the HTML search page shows up to 8
   instructions plus up to 3 related articles.

Scores are cosine similarities for ranking only. They are not probabilities.

**Known limitation: no relevance floor.** With the default model, unrelated queries still score about
0.6-0.77 against *something*, which overlaps the scores of genuine but weak matches (verified with 4 pages).
So the app always shows the top results and says they may be weak. Revisit once there are 50+ pages, by
calibrating a threshold with `content/eval.yaml` plus negative examples.

### Why these choices

- **fastembed + `BAAI/bge-small-en-v1.5`**: ONNX runtime, no PyTorch (the image is ~640 MB instead of GBs),
  CPU-only, ~9 ms per query in a 1-CPU container. Model and `model_name` are configurable, but changing the
  model requires rebuilding the index (the index records the embedder id and the app refuses a mismatch).
- **No vector database**: nothing to operate, nothing stateful on Kubernetes, results are exact.
- **Server-rendered HTML, no JS**: simple, fast, indexable, trivially cacheable. Tailwind is a build-time tool only, and code blocks are coloured on the server with Pygments rather than by a script in the browser.
- **Index built at image build time**: the image is immutable and self-consistent; content, index and model
  can never drift apart in a running pod.

## Index freshness contract

`index/meta.json` stores the embedder id and a SHA-256 of all search-unit texts. At startup:

- fresh -> serve;
- stale or missing and `DOCX86_REBUILD_STALE_INDEX` unset (**production default**) -> `IndexStaleError`, the
  process exits non-zero, the pod never becomes Ready, and a Kubernetes rollout stalls on the old pods;
- stale and `DOCX86_REBUILD_STALE_INDEX=1` (`make dev` sets it) -> rebuild in place.

Verified: running the image against edited content without rebuilding exits with code 3 and
`content changed since the index was built (run make index)`. Editing prose that is not in any search unit
(forms, flags, Gotchas, Example) does not invalidate the index.

## HTTP surface

| Route | Purpose |
|---|---|
| `GET /` | Home with search box and example queries (taken from real `search_phrases`). |
| `GET /search?q=` | Ranked instruction results + related articles. Empty `q` redirects to `/`. |
| `GET /instructions`, `/instructions/{name}` | Browse by category; page. `{name}` may be a slug, mnemonic or alias in any case; non-canonical names 301 to the slug. |
| `GET /articles`, `/articles/{slug}` | Articles. |
| `GET /about` | Plain-language ("explain like I'm five") description of the search. The page counts and one real example search are computed at request time, so it cannot drift from the code; if you change how ranking works, update the wording in `templates/about.html`. |
| `GET /evidence`, `/instructions/{name}/evidence`, `/articles/{slug}/evidence` | Which source sentence supports which statement of a page (overview / per page, `?state=` filter). Pointers always; source passages only where the reader has the documents locally. See `docs/EVIDENCE.md`. |
| `GET /api/search?q=&kind=&limit=` | JSON. `q` 1-200 chars, `limit` 1-25 (default 8). Intended for tools and agents. |
| `GET /api/instructions`, `/api/instructions/{name}` | JSON list / full page (no rendered HTML). |
| `GET /api/evidence`, `/api/evidence/{instructions\|articles}/{slug}` | JSON coverage totals / one page's claims with their sources. |
| `GET /healthz` | Liveness: process is serving. |
| `GET /readyz` | Readiness: content and index loaded (returns counts). |
| `GET /docs` | FastAPI's generated OpenAPI UI. |

## Configuration

All settings are environment variables (`src/docx86/config.py`, prefix `DOCX86_`; a local `.env` is read in development).

| Variable | Default | Meaning |
|---|---|---|
| `DOCX86_CONTENT_DIR` | `<repo>/content` | Pages, articles, roster. |
| `DOCX86_INDEX_DIR` | `<repo>/index` | Built index. |
| `DOCX86_EMBEDDER` | `fastembed` | `fastembed` or `hash` (tests only). |
| `DOCX86_MODEL_NAME` | `BAAI/bge-small-en-v1.5` | fastembed model. |
| `DOCX86_MODEL_CACHE_DIR` | `<repo>/.cache/models` | Where the model lives (`/opt/models` in the image). |
| `DOCX86_MODEL_OFFLINE` | `false` | Never touch the network; load from the cache only (`1` in the image). |
| `DOCX86_EMBED_THREADS` | `1` | ONNX threads. onnxruntime otherwise sizes its pool by *node* cores and ignores the pod CPU limit, causing throttling. |
| `DOCX86_REBUILD_STALE_INDEX` | `false` | Dev convenience, see above. |
| `DOCX86_SDM_PDF` | `docs/docs.x86.pdf` | Used by `docx86 sdm` and the evidence tooling. |
| `DOCX86_TRACE_USER_DATA` | `false` | Keep the user's search text in traces (`url.query`, `docx86.search.query`). Off by default; see *Observability*. |
| `DOCX86_WIKIBOOKS_HTML` | `docs/wikibooks_x86.html` | Used by `docx86 wiki` and the evidence tooling. |
| `DOCX86_SYSV_ABI_PDF` | `docs/sysv_abi.pdf` | System V AMD64 ABI; evidence tooling only. |
| `DOCX86_MS_CALLING_CONVENTION_HTML` | `docs/ms_x64_calling_convention.html` | Microsoft x64 calling convention page; evidence tooling only. |
| `DOCX86_MS_STACK_USAGE_HTML` | `docs/ms_x64_stack_usage.html` | Microsoft x64 stack usage page; evidence tooling only. |
| `DOCX86_CACHE_DIR` | `<repo>/.cache` | Extracted source sentences (`units/`); safe to delete. Unwritable is fine. |
| `DOCX86_LOG_LEVEL` | `INFO` | Python log level. |

Tracing is configured with the standard `OTEL_*` variables instead; see *Observability*.

## Observability (OpenTelemetry tracing)

Traces only (no metrics or logs signal). **Off until an exporter is configured**; when off, the code runs on
no-op tracers and costs nothing. Configuration is the standard OpenTelemetry environment:

| Variable | Effect |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Setting this turns tracing on and exports over **OTLP/HTTP protobuf** (collector port **4318**; not gRPC 4317). The SDK appends `/v1/traces`. |
| `OTEL_TRACES_EXPORTER` | `otlp` (default when an endpoint is set), `console` (print spans to stdout, for development) or `none`. Anything else fails startup. |
| `OTEL_SDK_DISABLED` | `true` forces tracing off. |
| `OTEL_SERVICE_NAME` | Defaults to `docx86`. `service.version` defaults to the app version. |
| `OTEL_RESOURCE_ATTRIBUTES` | Extra resource attributes. The Deployment sets `k8s.pod.name`, `k8s.namespace.name`, `k8s.node.name`, `service.instance.id` from the Downward API. |
| `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG` | Sampling. The manifest uses `parentbased_traceidratio` with `1.0`: a caller's sampling decision wins, otherwise keep every trace. |
| `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_TIMEOUT` | Auth headers for hosted backends (values must be percent-encoded; see below); export timeout in ms (the manifest uses 5000). |

Unsupported or inconsistent settings (`OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, an unknown exporter name) **fail startup**
with a message instead of silently exporting nothing. `OTEL_*` values in a local `.env` file are not read by the SDK;
export them in the shell.

### Where to set the collector URL and credentials

| Where | What to set |
|---|---|
| **Kubernetes** (the normal case) | In `deploy/k8s/kustomization.yaml`, uncomment `OTEL_EXPORTER_OTLP_ENDPOINT` in the `configMapGenerator` literals, then `kubectl apply -k deploy/k8s`. The ConfigMap name carries a hash, so the pods roll automatically. |
| **Credentials / auth headers** | Not in the ConfigMap. The Deployment optionally reads a Secret named `docx86-otel`: `kubectl -n docx86 create secret generic docx86-otel --from-literal=OTEL_EXPORTER_OTLP_HEADERS='authorization=Bearer%20<token>'`, then `kubectl -n docx86 rollout restart deploy/docx86` (pods that started before the Secret existed do not see it). |
| **Local run** | Export in the shell before `make dev`, e.g. `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 make dev`, or `OTEL_TRACES_EXPORTER=console` to print spans. A `.env` file is **not** read for `OTEL_*`. |
| **`docker run`** | `-e OTEL_EXPORTER_OTLP_ENDPOINT=...`. |

Endpoint rules (verified against the exporter):

- `OTEL_EXPORTER_OTLP_ENDPOINT` is the collector's **base URL**; `/v1/traces` is appended. In-cluster that is typically
  `http://<service>.<namespace>.svc.cluster.local:4318`. Use port **4318** (OTLP/HTTP), not 4317 (gRPC).
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, if you set it instead, is used **exactly as written**, path included.
- Header values must be **percent-encoded**: `authorization=Bearer%20abc` works, while `authorization=Bearer abc` is
  silently parsed as *no headers at all* (the SDK only logs "Header format invalid"), so nothing authenticates.
- If your collector runs as a node-local DaemonSet rather than a Service, the endpoint has to use the node's IP
  (the Downward API field `status.hostIP`). That is not wired up here because it depends on your setup.

### What gets traced

HTTP server spans come from **FastAPI's built-in telemetry** (FastAPI 0.142+), not the contrib instrumentation package.
They use the stable semantic conventions and the route template as the span name (`GET /instructions/{name}`), and
they continue an incoming W3C `traceparent` (verified end to end), so a trace started by an ingress controller or a
browser joins the backend's. `/healthz`, `/readyz` and `/static/` are not traced.

| Span | Where | Notable attributes |
|---|---|---|
| `GET /api/search` etc. (server) | FastAPI | `http.route`, `http.response.status_code`, `url.path`, `url.query` (with `q` redacted) |
| `fastapi.dependencies`, `fastapi.endpoint`, `fastapi.serialization` | FastAPI | `code.function.name` |
| `search` | `SearchEngine.search` | `docx86.search.kind`, `.limit`, `.query_length`, `.results`, `.top_slug`, `.top_score`, `.top_match` |
| `embed_query` | child of `search` | `docx86.embedder`. **Absent = the vector came from the cache.** |
| `engine.build` (at startup, own trace) | `build_engine` | `docx86.instructions`, `.articles`, `.index_units`, `.embedder`, `.index_rebuilt`; children `content.load`, `embedder.init` (model load, the slow part), `index.load` |

A failed startup (for example the stale-index crash) is exported too, with the exception recorded on `engine.build`, because
the provider is shut down in a `finally`.

### Privacy

By default **no search text and no client address reach the trace backend.** The query travels in `?q=` and FastAPI
records the query string in `url.query`; `telemetry.ScrubUserData` rewrites it to `q=REDACTED` (keeping `limit`, `kind`)
as each span starts, and also scrubs client-address attributes if a future version adds them. `DOCX86_TRACE_USER_DATA=true`
disables the scrubbing and adds `docx86.search.query`. Decide that consciously: search text is user input.

### Design notes and failure behaviour

- **FastAPI's own exporters are switched off** (`auto_configure=False`, `metrics=False`, `logs=False`). Left on, it reads
  `OTEL_EXPORTER_OTLP_ENDPOINT` and also ships *metrics and logs* to the collector, and its logs signal records validation
  errors together with the user's original input. It also added a metrics exporter whose retries delayed shutdown by 6.5 s.
- **A dead collector does not slow requests** (measured 7-9 ms per request with the endpoint refusing connections). Export runs
  on a background thread and drops spans when its queue is full.
- **Shutdown flushes buffered spans** on SIGTERM (measured 0.2 s with a healthy collector). With the collector down, shutdown
  takes up to about 8 s while the exporter retries, bounded by `OTEL_EXPORTER_OTLP_TIMEOUT`; the pod's 30 s grace period
  covers this together with the 5 s `preStop`.
- **Browser frontend (not built yet):** the backend already continues `traceparent`. A browser calling it cross-origin would
  also need CORS configured to allow the `traceparent`, `tracestate` and `baggage` request headers. There is no CORS config today.
- **Not included:** metrics, log correlation (trace ids in log lines), browser instrumentation, gRPC export.

## Container image

Multi-stage `Dockerfile` (about 640 MB):

1. `css`: Node builds Tailwind output (`npm ci`, lockfile pinned).
2. `build`: `uv sync --frozen` (lockfile pinned), copies content, runs `docx86 build-index` (downloads the
   model into `/opt/models` and writes `/app/index`), `docx86 validate` and `docx86 evidence check --no-sources`
   (stale claims, malformed ledgers). A content error fails the image build.
3. runtime: `python:3.13-slim`, UID/GID 10001, no shell login, copies only venv + src + content + index +
   models + CSS. The reference documents (SDM, ABI, Microsoft pages), tests, Node and uv are not in it, so the evidence pages show
   pointers but no source text there.

Verified: the image runs with `--network none --read-only --cap-drop ALL --user 10001 --memory 512m`, becomes
ready, serves search in about 9 ms, uses about 256 MiB, and logs no warnings.

## Kubernetes (`deploy/k8s`, kustomize)

```bash
make image IMAGE=<registry>/docx86 TAG=0.1.0 && docker push <registry>/docx86:0.1.0
$EDITOR deploy/k8s/kustomization.yaml    # images: newName / newTag
$EDITOR deploy/k8s/ingress.yaml          # host, ingressClassName, TLS
kubectl kustomize deploy/k8s             # review
kubectl apply -k deploy/k8s
```

| Object | Notes |
|---|---|
| Namespace `docx86` | Labelled Pod Security `restricted`; the pod spec satisfies it (non-root, seccomp `RuntimeDefault`, no privilege escalation, all capabilities dropped). |
| Deployment | 2 replicas, `maxUnavailable: 0`, read-only root filesystem with a 64 Mi `emptyDir` on `/tmp`, no service-account token, `preStop: sleep 5` so endpoints drain before SIGTERM, topology spread across nodes. Requests 100m CPU / 320 Mi, limits 1 CPU / 512 Mi (steady state is about 256 MiB). |
| Probes | `startupProbe` and `readinessProbe` -> `/readyz`; `livenessProbe` -> `/healthz`. |
| Service | ClusterIP, port 80 -> container `http` (8000). |
| Ingress | One host, `/` prefix. **Placeholder host `docx86.example.com`**: edit before applying. |
| PodDisruptionBudget | `minAvailable: 1`. |
| ConfigMap | Generated by kustomize with a content-hash suffix, so changing a value rolls the pods. Holds the `OTEL_*` sampler/timeout settings; **tracing stays off until you uncomment `OTEL_EXPORTER_OTLP_ENDPOINT`** in `kustomization.yaml`. |

Deliberately not included (add when needed): HorizontalPodAutoscaler (needs metrics-server; it also
conflicts with a fixed `replicas`), NetworkPolicy (depends on your CNI and ingress namespace; the app needs no
egress), TLS/cert-manager config, Prometheus metrics, rate limiting (do it at the ingress), CI/CD.

The app is stateless, so scaling is just `replicas`. Content changes ship as a new image tag.

## Testing

- `make test`: pytest with the hash embedder; no network or model needed. Covers content validation,
  search behaviour, index staleness, every HTTP route, progress generation, and checks on the real `content/`
  (including that the generated progress files are current, and, if the PDF is present, that every roster
  SDM title exists in it).
- Evidence: `test_textunits`, `test_claims`, `test_sources` (synthetic PDF and HTML documents), `test_evidence`, `test_suggest`, `test_evidence_web`, `test_evidence_cli`, and `test_real_evidence`, which checks the repository's own ledgers (valid, nothing stale, no source text, curated pages fully accounted for) and, where the documents are downloaded, that every pointer resolves.
- `tests/test_telemetry.py` checks span structure and parentage, `traceparent` continuation, that probes are not traced, the privacy defaults (the query text appears in no span attribute), that only traces are exported, and the `OTEL_*` handling.
- `make verify-asm`: builds the toolchain image in `tests/asm/Dockerfile` (NASM, binutils, GCC, MinGW-w64, Wine), then
  assembles, links and runs every example program from the articles and compares the output with `expected_*.txt`
  (Linux natively, Windows under Wine). Needs Docker and network on first build; not part of `make check`.
  `tests/test_asm_examples.py` is its fast companion: it checks, without Docker, that long `nasm` listings in articles
  exist in `tests/asm/`.
- `make eval`: runs `content/eval.yaml` against the real model; fails if an expected page is outside the top 3.
  With few pages top-3 is a weak bar; tighten it as the corpus grows.
- `make check` = lint + test + validate + evidence + progress freshness. Run it before committing.
