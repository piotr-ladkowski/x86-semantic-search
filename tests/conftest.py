"""Shared fixtures. Tests use the hash embedder, so they need no model download or network."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from docx86.config import Settings
from docx86.main import build_engine, create_app

SECTIONS = {
    "What it does": "Does a thing.",
    "When to use it": "- When you need the thing.",
    "Gotchas": "- Be careful.",
    "Example": "```nasm\nnop\n```",
}


def page_md(
    slug: str,
    mnemonic: str | None = None,
    *,
    aliases: tuple[str, ...] = (),
    category: str = "logical",
    phrases: tuple[str, ...] = ("first phrase", "second phrase", "third phrase"),
    sections: dict[str, str] | None = None,
    related: tuple[str, ...] = (),
    body_prefix: str = "",
) -> str:
    mnemonic = mnemonic or slug.upper()
    front = {
        "slug": slug,
        "mnemonic": mnemonic,
        "aliases": list(aliases),
        "title": f"Title of {mnemonic}",
        "summary": f"Summary of {mnemonic}.",
        "category": category,
        "status": "draft",
        "sdm_entries": [f"{mnemonic}—Test"],
        "forms": [{"syntax": f"{mnemonic} r64, r/m64", "opcode": "REX.W + 00 /r"}],
        "search_phrases": list(phrases),
        "related": list(related),
    }
    secs = SECTIONS if sections is None else sections
    body = body_prefix + "".join(f"## {k}\n\n{v}\n\n" for k, v in secs.items())
    return "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n\n" + body


ARTICLE = """---
slug: regs
title: About registers
summary: How registers behave.
tags: [registers]
related_instructions: [popcnt]
search_phrases: [register behaviour]
---

Registers hold values.

## Detail

More detail.
"""

DEFAULT_PAGES = [
    {
        "slug": "popcnt",
        "category": "bit-byte",
        "phrases": ("count the number of set bits", "population count", "hamming weight"),
    },
    {
        "slug": "lea",
        "category": "miscellaneous",
        "phrases": ("calculate an address", "pointer arithmetic", "load effective address"),
    },
    {
        "slug": "shl",
        "aliases": ("SAL",),
        "category": "shift-rotate",
        "phrases": ("shift bits left", "multiply by a power of two", "logical shift left"),
        "related": ("rol",),
    },
]


def write_content(
    root: Path,
    pages: list[dict] | None = None,
    *,
    articles: dict[str, str] | None = None,
    extra_roster: tuple[str, ...] = ("rol",),
) -> Path:
    pages = DEFAULT_PAGES if pages is None else pages
    (root / "instructions").mkdir(parents=True, exist_ok=True)
    (root / "articles").mkdir(parents=True, exist_ok=True)
    roster = []
    for spec in pages:
        (root / "instructions" / f"{spec['slug']}.md").write_text(page_md(**spec), encoding="utf-8")
        m = spec.get("mnemonic") or spec["slug"].upper()
        roster.append(
            {
                "slug": spec["slug"],
                "mnemonic": m,
                "category": spec.get("category", "logical"),
                "sdm": [f"{m}—Test"],
            }
        )
    for slug in extra_roster:
        roster.append(
            {
                "slug": slug,
                "mnemonic": slug.upper(),
                "category": "shift-rotate",
                "sdm": [f"{slug.upper()}—Test"],
            }
        )
    for slug, text in (articles if articles is not None else {"regs": ARTICLE}).items():
        (root / "articles" / f"{slug}.md").write_text(text, encoding="utf-8")
    (root / "roster.yaml").write_text(
        yaml.safe_dump({"sdm_revision": "test-rev", "instructions": roster}, allow_unicode=True),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    return write_content(tmp_path / "content")


@pytest.fixture
def settings(tmp_path: Path, content_dir: Path) -> Settings:
    return Settings(
        content_dir=content_dir,
        index_dir=tmp_path / "index",
        embedder="hash",
        rebuild_stale_index=True,
    )


@pytest.fixture
def engine(settings: Settings):
    return build_engine(settings)


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as c:
        yield c
