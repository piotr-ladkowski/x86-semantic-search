"""Vector index: build from content, persist to disk, load, and detect staleness.

On-disk layout of an index directory (all produced by `docx86 build-index`):
    units.json    [{"slug", "kind", "text"}, ...]   one entry per embedded text
    vectors.npy   float32 (n_units, dim), L2-normalised, row i embeds units[i]
    meta.json     {"embedder", "dim", "content_hash", "n_units"}

Each page contributes several units (a summary unit plus one per `search_phrases` entry), so a
short natural-language query can match a phrase directly. Search takes the best unit per page.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .content import Content
from .embedding import Embedder


class IndexStaleError(RuntimeError):
    """The index on disk does not match the content/embedder. Run `make index`."""


@dataclass(frozen=True)
class SearchUnit:
    slug: str
    kind: str  # "instruction" | "article"
    text: str


@dataclass
class Index:
    units: list[SearchUnit]
    vectors: np.ndarray
    embedder_id: str
    content_hash: str


def build_units(content: Content) -> list[SearchUnit]:
    units: list[SearchUnit] = []
    for slug, ins in content.instructions.items():
        names = ", ".join(ins.all_mnemonics)
        main = f"{names} — {ins.title}. {ins.summary}\n{ins.sections['What it does']}\n"
        main += ins.sections["When to use it"]
        units.append(SearchUnit(slug, "instruction", main))
        units.extend(SearchUnit(slug, "instruction", p) for p in ins.search_phrases)
    for slug, art in content.articles.items():
        units.append(SearchUnit(slug, "article", f"{art.title}. {art.summary}\n{art.body_md}"))
        units.extend(SearchUnit(slug, "article", p) for p in art.search_phrases)
    return units


def units_hash(units: list[SearchUnit]) -> str:
    payload = json.dumps([[u.slug, u.kind, u.text] for u in units], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_index(content: Content, embedder: Embedder) -> Index:
    units = build_units(content)
    vectors = embedder.embed_documents([u.text for u in units])
    return Index(units, vectors, embedder.id, units_hash(units))


def save_index(index: Index, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    units = [{"slug": u.slug, "kind": u.kind, "text": u.text} for u in index.units]
    (directory / "units.json").write_text(json.dumps(units, ensure_ascii=False), encoding="utf-8")
    np.save(directory / "vectors.npy", index.vectors.astype(np.float32))
    meta = {
        "embedder": index.embedder_id,
        "dim": int(index.vectors.shape[1]),
        "content_hash": index.content_hash,
        "n_units": len(index.units),
    }
    (directory / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load_index(directory: Path) -> Index:
    try:
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        raw = json.loads((directory / "units.json").read_text(encoding="utf-8"))
        vectors = np.load(directory / "vectors.npy")
    except FileNotFoundError as err:
        raise IndexStaleError(f"no index in {directory} (run `make index`)") from err
    units = [SearchUnit(u["slug"], u["kind"], u["text"]) for u in raw]
    return Index(units, vectors, meta["embedder"], meta["content_hash"])


def ensure_fresh(index: Index, content: Content, embedder: Embedder) -> None:
    if index.embedder_id != embedder.id:
        raise IndexStaleError(
            f"index was built with '{index.embedder_id}' but the app uses '{embedder.id}' "
            "(run `make index`)"
        )
    if index.content_hash != units_hash(build_units(content)):
        raise IndexStaleError("content changed since the index was built (run `make index`)")
