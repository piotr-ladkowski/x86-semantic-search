"""Query-time search: dense retrieval with an exact-mnemonic override and boost."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
from opentelemetry.trace import NoOpTracer, Tracer

from .content import Content
from .embedding import Embedder
from .index import Index

# A mnemonic that appears as a token in a longer query nudges that page up. It must stay small:
# mnemonics like AND/OR/NOT/CALL are also ordinary English words in natural-language queries.
MNEMONIC_TOKEN_BOOST = 0.08


@dataclass(frozen=True)
class Hit:
    slug: str
    kind: str
    score: float  # cosine similarity (+ boost). Ranking only; not a calibrated probability.
    match: Literal["mnemonic", "semantic"]
    via: str | None = None  # the indexed text that matched best (useful when debugging relevance)


class SearchEngine:
    def __init__(
        self,
        content: Content,
        index: Index,
        embedder: Embedder,
        *,
        tracer: Tracer | None = None,
        record_query: bool = False,
    ):
        self.content = content
        self.index = index
        self.embedder = embedder
        self.tracer = tracer or NoOpTracer()
        self.record_query = record_query  # put the user's query text on spans (off: privacy)
        self._slugs = np.array([u.slug for u in index.units])
        self._kinds = np.array([u.kind for u in index.units])
        # The HTML results page searches twice (instructions, then articles) for one query, and
        # popular queries repeat. Cache query vectors; a trace with no `embed_query` span under
        # `search` was served from this cache.
        self._embed_query = lru_cache(maxsize=512)(self._embed_query_uncached)

    def _embed_query_uncached(self, text: str) -> np.ndarray:
        with self.tracer.start_as_current_span(
            "embed_query", attributes={"docx86.embedder": self.embedder.id}
        ):
            vec = self.embedder.embed_query(text)
        vec.setflags(write=False)  # shared between callers via the cache
        return vec

    def search(self, query: str, *, kind: str | None = None, limit: int = 8) -> list[Hit]:
        query = " ".join(query.split())
        if not query:
            return []
        with self.tracer.start_as_current_span("search") as span:
            span.set_attribute("docx86.search.kind", kind or "any")
            span.set_attribute("docx86.search.limit", limit)
            span.set_attribute("docx86.search.query_length", len(query))
            if self.record_query:
                span.set_attribute("docx86.search.query", query)
            hits = self._search(query, kind, limit)
            span.set_attribute("docx86.search.results", len(hits))
            if hits:
                span.set_attribute("docx86.search.top_slug", hits[0].slug)
                span.set_attribute("docx86.search.top_score", round(hits[0].score, 4))
                span.set_attribute("docx86.search.top_match", hits[0].match)
            return hits

    def _search(self, query: str, kind: str | None, limit: int) -> list[Hit]:
        pinned: list[Hit] = []
        if kind in (None, "instruction") and (ins := self.content.resolve(query)):
            pinned.append(Hit(ins.slug, "instruction", 1.0, "mnemonic"))

        sims = self.index.vectors @ self._embed_query(query)
        if kind:
            sims = np.where(self._kinds == kind, sims, -np.inf)

        best: dict[tuple[str, str], tuple[float, int]] = {}  # (kind, slug) -> (score, unit row)
        for row in np.argsort(-sims):
            if not np.isfinite(sims[row]):
                break
            best.setdefault(
                (str(self._kinds[row]), str(self._slugs[row])), (float(sims[row]), int(row))
            )

        token_slugs = {
            slug
            for tok in re.findall(r"[A-Za-z0-9]+", query)
            if (slug := self.content.mnemonic_index.get(tok.lower()))
        }
        hits = []
        for (hit_kind, slug), (score, row) in best.items():
            boosted = hit_kind == "instruction" and slug in token_slugs
            hits.append(
                Hit(
                    slug,
                    hit_kind,
                    score + (MNEMONIC_TOKEN_BOOST if boosted else 0.0),
                    "mnemonic" if boosted else "semantic",
                    self.index.units[row].text,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)

        seen = {(h.kind, h.slug) for h in pinned}
        return (pinned + [h for h in hits if (h.kind, h.slug) not in seen])[:limit]
