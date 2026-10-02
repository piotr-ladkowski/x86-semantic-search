"""Break a page into its checkable statements ("claims").

Every sentence of prose, every table row, every code block and the structured facts in the front
matter (summary, forms, flags, aliases, CPUID requirement) is one claim. A claim's `id` is the
fingerprint of its wording, so the evidence ledger (`evidence.py`) attaches to exactly this text and
goes stale, visibly, when the text changes.

Not claims: titles, slugs, categories, status and `search_phrases` (they steer search, they assert
nothing), and the citations themselves (`sdm_entries`, `extra_sources`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from markdown_it import MarkdownIt

from .models import Article, Instruction
from .textunits import digest, split_sentences

_md = MarkdownIt("commonmark").enable("table")


@dataclass(frozen=True)
class Claim:
    id: str  # fingerprint of `text`
    text: str  # markdown of the sentence (inline formatting kept; shown rendered)
    section: str  # where on the page it lives: "Summary", "Forms", "Gotchas", ...
    kind: str  # "prose" | "row" | "code" | "fact" (structured front matter)
    header: tuple[str, ...] = field(default_factory=tuple)  # column names, for table rows


def _inline_text(token_content: str) -> str:
    return token_content.replace("\n", " ").strip()


def claims_from_markdown(markdown: str, default_section: str) -> list[Claim]:
    """Claims in a markdown body. `## Heading` lines switch the section label."""
    out: list[Claim] = []
    section = default_section
    tokens = _md.parse(markdown)
    in_table_header = False
    row_cells: list[str] = []
    header: list[str] = []
    in_row = False
    row_is_header = False
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            section = _inline_text(tokens[i + 1].content) if tok.tag in ("h2", "h3") else section
        elif tok.type == "thead_open":
            in_table_header = True
        elif tok.type == "thead_close":
            in_table_header = False
        elif tok.type == "tr_open":
            in_row, row_cells, row_is_header = True, [], in_table_header
        elif tok.type == "tr_close":
            in_row = False
            if row_is_header:
                header = row_cells
            elif any(row_cells):
                text = " | ".join(c for c in row_cells if c)
                out.append(Claim(digest(text), text, section, "row", tuple(header)))
        elif tok.type == "inline":
            prev = tokens[i - 1].type if i else ""
            if prev == "heading_open":
                continue
            if in_row:
                row_cells.append(_inline_text(tok.content))
            else:
                out.extend(
                    Claim(digest(s), s, section, "prose") for s in split_sentences(tok.content)
                )
        elif tok.type == "fence":
            code = tok.content.rstrip("\n")
            out.append(Claim(digest(code), code, section, "code"))
    return _dedupe(out)


def _dedupe(claims: list[Claim]) -> list[Claim]:
    seen: set[str] = set()
    unique = []
    for c in claims:
        if c.id not in seen:
            seen.add(c.id)
            unique.append(c)
    return unique


def _front_matter_claims(item: Instruction) -> list[Claim]:
    out = [Claim(digest(item.summary), item.summary, "Summary", "fact")]
    if item.aliases:
        text = "Also written as " + ", ".join(f"`{a}`" for a in item.aliases) + "."
        out.append(Claim(digest(text), text, "Aliases", "fact"))
    if item.cpuid_feature:
        text = f"Needs the {item.cpuid_feature} CPU feature (reported by CPUID)."
        out.append(Claim(digest(text), text, "Requirements", "fact"))
    for form in item.forms:
        text = f"`{form.syntax}` is encoded as `{form.opcode}`."
        out.append(Claim(digest(text), text, "Forms", "fact"))
        for s in split_sentences(form.note or ""):
            out.append(Claim(digest(s), s, "Forms", "prose"))
    f = item.flags
    parts = [
        f"{label}: {', '.join(vals)}"
        for label, vals in (("modified", f.modified), ("undefined", f.undefined), ("read", f.read))
        if vals
    ]
    if parts:
        text = "Flags " + "; ".join(parts) + "."
        out.append(Claim(digest(text), text, "Flags", "fact"))
    for s in split_sentences(f.note or ""):
        out.append(Claim(digest(s), s, "Flags", "prose"))
    return out


def claims_for_instruction(item: Instruction) -> list[Claim]:
    claims = _front_matter_claims(item)
    claims += claims_from_markdown(item.body_md, "Introduction")
    return _dedupe(claims)


def claims_for_article(item: Article) -> list[Claim]:
    claims = [Claim(digest(item.summary), item.summary, "Summary", "fact")]
    claims += claims_from_markdown(item.body_md, "Introduction")
    return _dedupe(claims)
