"""Server-rendered HTML pages (Jinja2 + Tailwind). No client-side JavaScript is required."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .api import DEFAULT_LIMIT, MAX_QUERY_LENGTH, Engine
from .models import Category

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(include_in_schema=False)

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
def instruction_page(request: Request, engine: Engine, name: str):
    c = engine.content
    ins = c.resolve(name)
    if ins is None:
        raise HTTPException(404)
    if name != ins.slug:  # alias, mnemonic or different case -> canonical URL
        return RedirectResponse(f"/instructions/{ins.slug}", status_code=301)
    related = [c.instructions[s] for s in ins.related if s in c.instructions]
    ctx = {"ins": ins, "related": related, "sdm_revision": c.roster.sdm_revision}
    return templates.TemplateResponse(request, "instruction.html", ctx)


@router.get("/articles", response_class=HTMLResponse)
def article_index(request: Request, engine: Engine):
    return templates.TemplateResponse(
        request, "articles.html", {"articles": list(engine.content.articles.values())}
    )


@router.get("/articles/{slug}", response_class=HTMLResponse)
def article_page(request: Request, engine: Engine, slug: str):
    c = engine.content
    art = c.articles.get(slug)
    if art is None:
        raise HTTPException(404)
    related = [c.instructions[s] for s in art.related_instructions if s in c.instructions]
    ctx = {"art": art, "related": related, "sdm_revision": c.roster.sdm_revision}
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
