"""Load and validate content/ (instruction pages, articles, roster).

`load_content` collects *every* problem before raising, so an author (human or LLM) sees the
full list from one run of `docx86 validate`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from markdown_it import MarkdownIt
from pydantic import ValidationError

from .highlight import highlight_code
from .models import Article, ArticleMeta, Instruction, InstructionMeta, Roster

REQUIRED_SECTIONS = ("What it does", "When to use it", "Gotchas", "Example")


def _highlight_fence(code: str, lang: str, _attrs: str) -> str:
    return highlight_code(code, lang)


# Raw HTML in Markdown stays disabled; highlighted code is produced (and escaped) by Pygments.
_md = MarkdownIt("commonmark", {"html": False, "highlight": _highlight_fence}).enable("table")


class ContentError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} content problem(s):\n" + "\n".join(problems))


@dataclass
class Content:
    instructions: dict[str, Instruction]
    articles: dict[str, Article]
    roster: Roster
    _by_name: dict[str, str] = field(default_factory=dict, repr=False)

    def resolve(self, name: str) -> Instruction | None:
        """Find an instruction by slug, mnemonic or alias (case-insensitive)."""
        slug = self._by_name.get(name.strip().lower())
        return self.instructions.get(slug) if slug else None

    @property
    def mnemonic_index(self) -> dict[str, str]:
        """lowercase mnemonic/alias/slug -> canonical slug."""
        return self._by_name


def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("file must start with a '---' YAML front matter block")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("front matter is not closed with a '---' line")
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise ValueError("front matter must be a YAML mapping")
    return data, text[end + 5 :].lstrip("\n")


def split_sections(body: str) -> tuple[dict[str, str], list[str]]:
    """Split markdown on top-level `##` headings (fence-aware). Returns (sections, problems)."""
    lines = body.splitlines()
    headings: list[tuple[int, str]] = []
    problems: list[str] = []
    tokens = _md.parse(body)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.level == 0 and tok.map:
            if tok.tag == "h1":
                problems.append(
                    "body must not contain an H1 ('# ...'); the title comes from front matter"
                )
            elif tok.tag == "h2":
                headings.append((tok.map[0], tokens[i + 1].content.strip()))
    sections: dict[str, str] = {}
    for idx, (start, name) in enumerate(headings):
        stop = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        if name in sections:
            problems.append(f"duplicate section '## {name}'")
        sections[name] = "\n".join(lines[start + 1 : stop]).strip()
    return sections, problems


def _has_code_fence(md_text: str) -> bool:
    return any(t.type == "fence" for t in _md.parse(md_text))


def _fmt_validation_error(path: Path, err: ValidationError) -> list[str]:
    return [
        f"{path}: {'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}"
        for e in err.errors()
    ]


def _load_instruction(path: Path, problems: list[str]) -> Instruction | None:
    try:
        raw, body = split_front_matter(path.read_text(encoding="utf-8"))
        meta = InstructionMeta.model_validate(raw)
    except ValidationError as err:
        problems.extend(_fmt_validation_error(path, err))
        return None
    except (ValueError, yaml.YAMLError) as err:
        problems.append(f"{path}: {err}")
        return None

    ok = True
    if path.stem != meta.slug:
        problems.append(f"{path}: filename must equal slug ('{meta.slug}.md')")
        ok = False
    sections, sec_problems = split_sections(body)
    problems.extend(f"{path}: {p}" for p in sec_problems)
    for name in REQUIRED_SECTIONS:
        if not sections.get(name):
            problems.append(f"{path}: missing or empty required section '## {name}'")
            ok = False
    if sections.get("Example") and not _has_code_fence(sections["Example"]):
        problems.append(f"{path}: '## Example' must contain a fenced code block")
        ok = False
    if sec_problems or not ok:
        return None
    return Instruction(
        **meta.model_dump(), body_md=body, body_html=_md.render(body), sections=sections
    )


def _load_article(path: Path, problems: list[str]) -> Article | None:
    try:
        raw, body = split_front_matter(path.read_text(encoding="utf-8"))
        meta = ArticleMeta.model_validate(raw)
    except ValidationError as err:
        problems.extend(_fmt_validation_error(path, err))
        return None
    except (ValueError, yaml.YAMLError) as err:
        problems.append(f"{path}: {err}")
        return None
    if path.stem != meta.slug:
        problems.append(f"{path}: filename must equal slug ('{meta.slug}.md')")
        return None
    _, sec_problems = split_sections(body)
    problems.extend(f"{path}: {p}" for p in sec_problems)
    if not body.strip():
        problems.append(f"{path}: article body is empty")
        return None
    return Article(**meta.model_dump(), body_md=body, body_html=_md.render(body))


def _check_cross_references(
    instructions: dict[str, Instruction], articles: dict[str, Article], roster: Roster
) -> tuple[list[str], dict[str, str]]:
    problems: list[str] = []
    names: dict[str, str] = {}

    def claim(name: str, slug: str, what: str) -> None:
        key = name.lower()
        if key in names and names[key] != slug:
            problems.append(f"{what} '{name}' of '{slug}' collides with '{names[key]}'")
        names.setdefault(key, slug)

    for slug, ins in instructions.items():
        claim(slug, slug, "slug")
        for m in ins.all_mnemonics:
            claim(m, slug, "mnemonic/alias")
    planned = {e.slug for e in roster.instructions}  # links may point at not-yet-written pages
    for slug, ins in instructions.items():
        for rel in ins.related:
            if rel not in planned:
                problems.append(f"{slug}: related '{rel}' is not a slug in content/roster.yaml")
    for slug, art in articles.items():
        for rel in art.related_instructions:
            if rel not in planned:
                problems.append(
                    f"article {slug}: related_instructions '{rel}' is not in the roster"
                )

    in_roster = {e.slug: e for e in roster.instructions}
    for slug, ins in instructions.items():
        entry = in_roster.get(slug)
        if entry is None:
            problems.append(
                f"{slug}: not in content/roster.yaml `instructions` (out of scope, or add it there)"
            )
            continue
        if ins.mnemonic != entry.mnemonic or ins.category != entry.category:
            problems.append(f"{slug}: mnemonic/category differ from roster entry")
        if sorted(ins.sdm_entries) != sorted(entry.sdm):
            problems.append(f"{slug}: sdm_entries differ from roster entry (copy them from it)")
    roster_slugs = [e.slug for e in roster.instructions]
    for dup in {s for s in roster_slugs if roster_slugs.count(s) > 1}:
        problems.append(f"roster: duplicate slug '{dup}'")
    return problems, names


def load_content(content_dir: Path) -> Content:
    problems: list[str] = []
    content_dir = Path(content_dir)

    roster_path = content_dir / "roster.yaml"
    try:
        roster = Roster.model_validate(yaml.safe_load(roster_path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise ContentError([f"{roster_path}: missing"]) from None
    except ValidationError as err:
        raise ContentError(_fmt_validation_error(roster_path, err)) from err

    instructions: dict[str, Instruction] = {}
    for path in sorted((content_dir / "instructions").glob("*.md")):
        if (ins := _load_instruction(path, problems)) is not None:
            instructions[ins.slug] = ins

    articles: dict[str, Article] = {}
    for path in sorted((content_dir / "articles").glob("*.md")):
        if (art := _load_article(path, problems)) is not None:
            articles[art.slug] = art

    xref_problems, names = _check_cross_references(instructions, articles, roster)
    problems.extend(xref_problems)
    if problems:
        raise ContentError(problems)
    return Content(instructions=instructions, articles=articles, roster=roster, _by_name=names)
