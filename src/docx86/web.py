"""Server-rendered HTML pages (Jinja2 + Tailwind). No client-side JavaScript is required."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup

from .api import DEFAULT_LIMIT, MAX_QUERY_LENGTH, Engine, Evidence, Sources
from .evidence import STATE_LABELS, STATES, passages
from .models import Category

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(include_in_schema=False)

_inline_md = MarkdownIt("commonmark", {"html": False})
templates.env.filters["inline_md"] = lambda text: Markup(_inline_md.renderInline(text))

ARTICLE_RESULTS = 3
# Run live on /about to show a real search. Deliberately not copied from any page's search_phrases.
ABOUT_EXAMPLE_QUERY = "how many 1s are in this number"


@router.get("/", response_class=HTMLResponse)
def home(request: Request, engine: Engine):
    c = engine.content
    examples = [i.search_phrases[0] for i in list(c.instructions.values())[:5]]
    ctx = {
        "examples": examples,
        "documented": len(c.instructions),
        "total": len(c.roster.instructions),
    }
    return templates.TemplateResponse(request, "home.html", ctx)


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, engine: Engine, q: str = ""):
    q = " ".join(q.split())[:MAX_QUERY_LENGTH]
    if not q:
        return RedirectResponse("/", status_code=303)
    c = engine.content
    instruction_hits = [
        (h, c.instructions[h.slug])
        for h in engine.search(q, kind="instruction", limit=DEFAULT_LIMIT)
    ]
    article_hits = [
        (h, c.articles[h.slug]) for h in engine.search(q, kind="article", limit=ARTICLE_RESULTS)
    ]
    ctx = {"q": q, "instructions": instruction_hits, "articles": article_hits}
    return templates.TemplateResponse(request, "search.html", ctx)


@router.get("/instructions", response_class=HTMLResponse)
def instruction_index(request: Request, engine: Engine):
    c = engine.content
    grouped: dict[Category, list] = defaultdict(list)
    for ins in c.instructions.values():
        grouped[ins.category].append(ins)
    groups = [
        (cat, sorted(grouped[cat], key=lambda i: i.mnemonic)) for cat in Category if cat in grouped
    ]
    ctx = {"groups": groups, "documented": len(c.instructions), "total": len(c.roster.instructions)}
    return templates.TemplateResponse(request, "instructions.html", ctx)


@router.get("/instructions/{name}", response_class=HTMLResponse)
def instruction_page(request: Request, engine: Engine, evidence: Evidence, name: str):
    c = engine.content
    ins = c.resolve(name)
    if ins is None:
        raise HTTPException(404)
    if name != ins.slug:  # alias, mnemonic or different case -> canonical URL
        return RedirectResponse(f"/instructions/{ins.slug}", status_code=301)
    related = [c.instructions[s] for s in ins.related if s in c.instructions]
    ctx = {
        "ins": ins,
        "related": related,
        "sdm_revision": c.roster.sdm_revision,
        "evidence": evidence.get("instruction", ins.slug),
    }
    return templates.TemplateResponse(request, "instruction.html", ctx)


@router.get("/articles", response_class=HTMLResponse)
def article_index(request: Request, engine: Engine):
    return templates.TemplateResponse(
        request, "articles.html", {"articles": list(engine.content.articles.values())}
    )


@router.get("/articles/{slug}", response_class=HTMLResponse)
def article_page(request: Request, engine: Engine, evidence: Evidence, slug: str):
    c = engine.content
    art = c.articles.get(slug)
    if art is None:
        raise HTTPException(404)
    related = [c.instructions[s] for s in art.related_instructions if s in c.instructions]
    ctx = {
        "art": art,
        "related": related,
        "sdm_revision": c.roster.sdm_revision,
        "evidence": evidence.get("article", art.slug),
    }
    return templates.TemplateResponse(request, "article.html", ctx)


@router.get("/about", response_class=HTMLResponse)
def about(request: Request, engine: Engine):
    """Plain-language explanation of the search, with live numbers and one real search."""
    c = engine.content
    example = [
        (h, c.instructions[h.slug])
        for h in engine.search(ABOUT_EXAMPLE_QUERY, kind="instruction", limit=3)
    ]
    ctx = {
        "documented": len(c.instructions),
        "total": len(c.roster.instructions),
        "articles": len(c.articles),
        "pins": len(engine.index.units),
        "example_query": ABOUT_EXAMPLE_QUERY,
        "example": example,
    }
    return templates.TemplateResponse(request, "about.html", ctx)


# ----- evidence: which sentence of which document supports which statement of a page -----


@router.get("/evidence", response_class=HTMLResponse)
def evidence_index(request: Request, evidence: Evidence, sources: Sources):
    ctx = {
        "pages": evidence.pages(),
        "totals": evidence.totals(),
        "states": STATES,
        "labels": STATE_LABELS,
        "documents": [(src.label, src.available) for src in sources.all()],
    }
    return templates.TemplateResponse(request, "evidence_index.html", ctx)


def _evidence_page(
    request: Request,
    engine: Engine,
    evidence: Evidence,
    sources: Sources,
    kind: str,
    slug: str,
    state: str,
):
    page = evidence.get(kind, slug)
    if page is None:
        raise HTTPException(404)
    wanted = state if state in STATES else ""
    shown = []
    for i, view in enumerate(page.claims, 1):
        if wanted and view.state != wanted:
            continue
        found = passages(view.entry, view.claim, sources) if view.entry else []
        shown.append((i, view, found))
    sections: dict[str, list] = {}
    for item in shown:
        sections.setdefault(item[1].claim.section, []).append(item)
    ctx = {
        "page": page,
        "sections": sections,
        "states": STATES,
        "labels": STATE_LABELS,
        "wanted": wanted,
        "counts": page.counts(),
        "documents_missing": [src.label for src in sources.all() if not src.available],
        "sdm_revision": engine.content.roster.sdm_revision,
    }
    return templates.TemplateResponse(request, "evidence.html", ctx)


@router.get("/instructions/{name}/evidence", response_class=HTMLResponse)
def instruction_evidence(
    request: Request,
    engine: Engine,
    evidence: Evidence,
    sources: Sources,
    name: str,
    state: str = "",
):
    ins = engine.content.resolve(name)
    if ins is None:
        raise HTTPException(404)
    if name != ins.slug:
        return RedirectResponse(f"/instructions/{ins.slug}/evidence", status_code=301)
    return _evidence_page(request, engine, evidence, sources, "instruction", ins.slug, state)


@router.get("/articles/{slug}/evidence", response_class=HTMLResponse)
def article_evidence(
    request: Request,
    engine: Engine,
    evidence: Evidence,
    sources: Sources,
    slug: str,
    state: str = "",
):
    return _evidence_page(request, engine, evidence, sources, "article", slug, state)
