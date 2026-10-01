"""JSON API under /api (also what other tools and LLM agents should call)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .search import Hit, SearchEngine

MAX_QUERY_LENGTH = 200
DEFAULT_LIMIT = 8
MAX_LIMIT = 25

router = APIRouter(tags=["api"])


def get_engine(request: Request) -> SearchEngine:
    return request.app.state.engine


Engine = Annotated[SearchEngine, Depends(get_engine)]


def hit_to_dict(engine: SearchEngine, hit: Hit) -> dict:
    base = {"slug": hit.slug, "kind": hit.kind, "score": round(hit.score, 4), "match": hit.match}
    if hit.kind == "instruction":
        ins = engine.content.instructions[hit.slug]
        return base | {
            "mnemonic": ins.mnemonic,
            "title": ins.title,
            "summary": ins.summary,
            "category": ins.category.value,
            "status": ins.status.value,
            "url": f"/instructions/{ins.slug}",
        }
    art = engine.content.articles[hit.slug]
    return base | {
        "title": art.title,
        "summary": art.summary,
        "status": art.status.value,
        "url": f"/articles/{art.slug}",
    }


@router.get("/search")
def search(
    engine: Engine,
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH)],
    kind: Literal["instruction", "article"] | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> dict:
    """Semantic search. `q` is free text ('count the set bits') or a mnemonic ('popcnt')."""
    hits = engine.search(q, kind=kind, limit=limit)
    return {"query": q, "results": [hit_to_dict(engine, h) for h in hits]}


@router.get("/instructions")
def list_instructions(engine: Engine) -> dict:
    return {
        "results": [
            {
                "slug": i.slug,
                "mnemonic": i.mnemonic,
                "title": i.title,
                "summary": i.summary,
                "category": i.category.value,
                "status": i.status.value,
            }
            for i in engine.content.instructions.values()
        ]
    }


@router.get("/instructions/{name}")
def get_instruction(engine: Engine, name: str) -> dict:
    """Full page by slug, mnemonic or alias."""
    ins = engine.content.resolve(name)
    if ins is None:
        raise HTTPException(404, f"No documented instruction '{name}'")
    return ins.model_dump(mode="json", exclude={"body_html"})
