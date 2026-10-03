"""Find candidate source sentences for a page's claims (an authoring aid; never run by the web app).

Two kinds of candidate, deliberately kept apart because they deserve different trust:

  match    mechanical and exact: a form claim ("`ADD r/m64, r64` is encoded as `REX.W + 01 /r`") is
           looked up as a row of an SDM opcode table that holds the same opcode and syntax.
  similar  a ranking: sentence-embedding cosine plus overlap of the words that carry meaning. It
           proposes where to look. A human or an LLM reading the passage decides.

Recorded as evidence they become `by: match` and `by: auto` respectively, so a reader of the ledger
(and of the web page) can always tell a confirmed link from a guess.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from .claims import Claim
from .embedding import Embedder
from .evidence import Entry, PageEvidence, Support, key_terms, plain_text, quotable
from .sources import Located, SourceRegistry
from .textunits import squash

_FORM_CLAIM = re.compile(r"^`(?P<syntax>[^`]+)` is encoded as `(?P<opcode>[^`]+)`\.$")


@dataclass(frozen=True)
class PoolUnit:
    doc: str
    at: int | str
    loc: Located

    @property
    def text(self) -> str:
        return self.loc.unit.text


@dataclass(frozen=True)
class Candidate:
    score: float
    method: str  # "match" | "similar"
    unit: PoolUnit

    def support(self) -> Support:
        u = self.unit
        return Support(
            doc=u.doc,  # type: ignore[arg-type]
            at=u.at,
            units=[u.loc.unit.id],
            part=u.loc.unit.part or None,
            by="match" if self.method == "match" else "auto",
            quotes={u.loc.unit.id: u.text} if quotable(u.loc.unit) else {},
        )


def parse_scope(spec: str) -> tuple[str, str]:
    """'sdm:1234-1236' / 'sysv:16' / 'msx64:*' / 'wikibooks:Some section' -> (doc, locator spec)."""
    doc, _, rest = spec.partition(":")
    if not rest:
        raise ValueError(f"scope {spec!r} must look like doc:pages (sdm:79-80, msx64:*)")
    return doc, rest


def build_pool(registry: SourceRegistry, scope: list[str]) -> list[PoolUnit]:
    """Every unit of the named pages/sections."""
    pool: list[PoolUnit] = []
    for spec in scope:
        doc, rest = parse_scope(spec)
        source = registry[doc]
        if not source.available:
            raise FileNotFoundError(f"{source.label} is not available: {source.download}")
        locators: list[int | str]
        if doc in ("sdm", "sysv"):
            first, _, last = rest.partition("-")
            locators = list(range(int(first), int(last or first) + 1))
        elif rest == "*":
            locators = list(source.section_titles())  # type: ignore[attr-defined]
        else:
            locators = [rest]
        for at in locators:
            pool += [PoolUnit(doc, at, loc) for loc in source.units(at)]
    seen: set[tuple[str, str]] = set()  # the SDM repeats sentences (exceptions, per mode)
    unique = []
    for p in pool:
        key = (p.doc, p.loc.unit.id)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _syntax_variants(syntax: str) -> list[str]:
    """'MOVSB  (MOVS m8, m8)' is also written 'MOVS m8, m8' (and plain 'MOVSB') in the SDM."""
    inner = re.search(r"\(([^)]+)\)", syntax)
    outer = re.sub(r"\([^)]*\)", "", syntax).strip()
    return [syntax] + ([inner.group(1), outer] if inner else [])


def exact_form_match(claim: Claim, pool: list[PoolUnit]) -> Candidate | None:
    m = _FORM_CLAIM.match(claim.text)
    if not m:
        return None
    # The SDM prefixes some opcodes with "NP" (no mandatory prefix): "NP 90 | NOP".
    opcodes = [squash(m["opcode"]), "np" + squash(m["opcode"])]
    wants = {o + squash(syn) for o in opcodes for syn in _syntax_variants(m["syntax"])}
    for p in pool:
        if p.doc != "sdm" or p.loc.unit.kind != "row":
            continue
        row = squash(p.text)
        if any(row.startswith(w) for w in wants):
            return Candidate(1.0, "match", p)
    return None


def _lexical(claim_terms: set[str], unit_terms: set[str], idf: dict[str, float]) -> float:
    shared = claim_terms & unit_terms
    if not shared:
        return 0.0
    weight = sum(idf.get(t, 1.0) for t in shared)
    norm = math.sqrt(
        sum(idf.get(t, 1.0) for t in claim_terms) * sum(idf.get(t, 1.0) for t in unit_terms)
    )
    return weight / norm if norm else 0.0


def rank(
    claims: list[Claim], pool: list[PoolUnit], embedder: Embedder, top: int = 3
) -> dict[str, list[Candidate]]:
    """Best `top` pool units per claim (code claims are skipped: nothing to quote)."""
    if not pool:
        return {}
    targets = [c for c in claims if c.kind != "code"]
    if not targets:
        return {}
    unit_terms = [key_terms(p.text) for p in pool]
    df: dict[str, int] = {}
    for terms in unit_terms:
        for t in terms:
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log(1 + len(pool) / n) for t, n in df.items()}
    pool_vecs = embedder.embed_documents([p.text for p in pool])
    claim_vecs = embedder.embed_documents([plain_text(c.text) for c in targets])
    cos = claim_vecs @ pool_vecs.T
    out: dict[str, list[Candidate]] = {}
    for i, c in enumerate(targets):
        ct = key_terms(c.text)
        lex = np.array([_lexical(ct, ut, idf) for ut in unit_terms])
        score = 0.5 * np.clip(cos[i], 0, 1) + 0.5 * lex
        order = np.argsort(-score)[:top]
        out[c.id] = [Candidate(float(score[j]), "similar", pool[j]) for j in order]
    return out


def suggest(
    page: PageEvidence, pool: list[PoolUnit], embedder: Embedder, top: int = 3
) -> dict[str, list[Candidate]]:
    """Candidates for the page's claims that are not yet checked or confirmed."""
    todo = [v.claim for v in page.claims if v.state in ("unverified", "suggested")]
    found: dict[str, list[Candidate]] = {}
    rest = []
    for c in todo:
        exact = exact_form_match(c, pool)
        if exact:
            found[c.id] = [exact]
        else:
            rest.append(c)
    found.update(rank(rest, pool, embedder, top))
    return found


def entries_from(
    found: dict[str, list[Candidate]], *, min_score: float, per_claim: int = 1
) -> list[Entry]:
    """Ledger entries for the strong candidates (exact matches always qualify)."""
    out = []
    for claim_id, cands in found.items():
        keep = [c for c in cands if c.method == "match" or c.score >= min_score][:per_claim]
        if keep:
            out.append(Entry(id=claim_id, how="source", support=[c.support() for c in keep]))
    return out
