"""JSON API under /api (also what other tools and LLM agents should call)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .build import BuildInfo
from .content import RosterLookup
from .evidence import EvidenceStore, page_to_dict
from .models import EXCLUSION_LABELS
from .scope import scope_hint
from .search import Hit, SearchEngine
from .sources import SourceRegistry

MAX_QUERY_LENGTH = 200
DEFAULT_LIMIT = 8
MAX_LIMIT = 25

router = APIRouter(tags=["api"])


def get_engine(request: Request) -> SearchEngine:
    return request.app.state.engine


def get_evidence(request: Request) -> EvidenceStore:
    return request.app.state.evidence


def get_sources(request: Request) -> SourceRegistry:
    return request.app.state.sources


def get_build(request: Request) -> BuildInfo:
    return request.app.state.build


Engine = Annotated[SearchEngine, Depends(get_engine)]
Evidence = Annotated[EvidenceStore, Depends(get_evidence)]
Sources = Annotated[SourceRegistry, Depends(get_sources)]
Build = Annotated[BuildInfo, Depends(get_build)]


def roster_to_dict(lookup: RosterLookup | None) -> dict | None:
    """The roster's answer for a query that names an instruction without a page."""
    if lookup is None:
        return None
    out: dict = {"status": lookup.status, "name": lookup.name, "note": lookup.note}
    if lookup.entry is not None:
        out |= {
            "slug": lookup.entry.slug,
            "title": lookup.entry.title,
            "category": lookup.entry.category.value,
        }
    if lookup.reason is not None:
        out["reason"] = lookup.reason
        if lookup.status == "excluded":
            out["reason_text"] = EXCLUSION_LABELS[lookup.reason]
    return out


def hit_to_dict(engine: SearchEngine, hit: Hit) -> dict:
    base = {
        "slug": hit.slug,
        "kind": hit.kind,
        "score": round(hit.score, 4),
        "match": hit.match,
        "via": hit.via,  # the indexed text that matched; None for an exact-mnemonic pin
        "via_kind": hit.via_kind,
        "weak": hit.weak,  # below the relevance floor
    }
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
    """Semantic search. `q` is free text ('count the set bits') or a mnemonic ('popcnt').

    `results` are ranked by `score`; a hit with `weak: true` scored below `floor` and is probably
    not what was asked for. `roster` is set when `q` names an instruction that has no page: it is
    `planned` (in scope, not written yet), `deferred` (scope undecided) or `excluded` (with why).
    `scope_hint` is set when `q` contains a word that points at an out-of-scope family (xmm, avx,
    float, msr, ...).
    """
    hits = engine.search(q, kind=kind, limit=limit)
    roster = engine.content.resolve_roster(q)
    hint = None if roster else scope_hint(q)
    return {
        "query": q,
        "floor": engine.floor,
        "roster": roster_to_dict(roster),
        "scope_hint": {"word": hint.word, "about": hint.about} if hint else None,
        "results": [hit_to_dict(engine, h) for h in hits],
    }


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
        lookup = engine.content.resolve_roster(name)
        why = f" ({lookup.name} is {lookup.status}; see /api/search?q={name})" if lookup else ""
        raise HTTPException(404, f"No documented instruction '{name}'{why}")
    return ins.model_dump(mode="json", exclude={"body_html"})


@router.get("/evidence")
def evidence_summary(evidence: Evidence) -> dict:
    """How many statements on each page are traced to a source sentence (counts only)."""
    return {
        "totals": evidence.totals(),
        "pages": [
            {
                "kind": p.kind,
                "slug": p.slug,
                "status": p.status,
                "total": p.total,
                "grounded": p.grounded,
                "open": p.open,
                "counts": p.counts(),
                "url": p.url,
            }
            for p in evidence.pages()
        ],
    }


@router.get("/evidence/{kind}/{slug}")
def evidence_for_page(
    evidence: Evidence, sources: Sources, kind: Literal["instructions", "articles"], slug: str
) -> dict:
    """Every statement of a page with the places it is derived from.

    Pointers are always present. Passages of the reference documents appear only on a machine
    that has its own copy of them (they are copyrighted and not part of this service).
    """
    page = evidence.get("instruction" if kind == "instructions" else "article", slug)
    if page is None:
        raise HTTPException(404, f"No {kind[:-1]} '{slug}'")
    return page_to_dict(page, sources)


@router.get("/version")
def version(build: Build) -> dict:
    """Which commit this server runs, when its image was built and when this server started.

    `commit`, `commit_url` and `built_at` are null outside a CI-built image. `started_at` is the
    nearest thing to a deployment time a pod can see (see `docx86/build.py`).
    """
    return build.to_dict()
