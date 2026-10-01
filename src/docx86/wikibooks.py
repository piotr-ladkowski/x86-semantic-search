"""Look up sections of the Wikibooks "x86 Assembly" print version (authoring aid, stdlib only).

The Intel SDM is the authority for what instructions *do*. It says nothing about assemblers,
operating systems or calling conventions; for those topics the secondary source is the Wikibooks
book (https://en.wikibooks.org/wiki/X86_Assembly/Print_Version, CC BY-SA). We read it with this
module and write original text: never copy its prose (share-alike licence), and cite the section
in `extra_sources`.

The book is largely 32-bit. Treat it as a map of what to check, and verify 64-bit claims with a
real toolchain or the primary ABI documents.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
SKIP_TAGS = {"script", "style"}
BLOCK_TAGS = {"p", "div", "li", "tr", "ul", "ol", "table", "dl", "dt", "dd", "br", "blockquote"}
# MediaWiki chrome that is not content.
SKIP_CLASSES = (
    "mw-editsection",
    "toc",
    "printfooter",
    "catlinks",
    "noprint",
    "mw-empty-elt",
    "navbox",
)


@dataclass(frozen=True)
class WikiSection:
    level: int  # 1-4, from the h1..h4 element
    title: str
    text: str  # plain text; <pre> blocks keep their line breaks


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[list] = [[0, "(preamble)", []]]
        self._skip_depth = 0  # >0 while inside script/style or a chrome element
        self._skip_stack: list[bool] = []
        self._pre = 0
        self._heading: int | None = None
        self._heading_text: list[str] = []

    @property
    def _out(self) -> list[str]:
        return self.sections[-1][2]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        skip = tag in SKIP_TAGS or any(c in SKIP_CLASSES for c in classes)
        if tag not in {"br", "img", "hr", "meta", "link", "input"}:
            self._skip_stack.append(skip)
            self._skip_depth += skip
        if self._skip_depth:
            return
        if tag in HEADINGS:
            self._heading, self._heading_text = HEADINGS[tag], []
        elif tag == "pre":
            self._pre += 1
            self._out.append("\n")
        elif tag in BLOCK_TAGS:
            self._out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack and tag not in {"br", "img", "hr", "meta", "link", "input"}:
            self._skip_depth -= self._skip_stack.pop()
        if self._skip_depth:
            return
        if tag in HEADINGS and self._heading is not None:
            title = re.sub(r"\s+", " ", "".join(self._heading_text)).replace("[edit]", "").strip()
            self.sections.append([self._heading, title, []])
            self._heading = None
        elif tag == "pre":
            self._pre = max(0, self._pre - 1)
            self._out.append("\n")
        elif tag in BLOCK_TAGS:
            self._out.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._heading is not None:
            self._heading_text.append(data)
        elif self._pre:
            self._out.append(data)
        else:
            self._out.append(re.sub(r"\s+", " ", data))


def _tidy(chunks: list[str]) -> str:
    text = "".join(chunks)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return html.unescape(text).strip()


def parse_sections(raw_html: str) -> list[WikiSection]:
    parser = _Extractor()
    parser.feed(raw_html)
    parser.close()
    # Level 0 is whatever precedes the first heading (page title, site chrome): not content.
    return [
        WikiSection(level, title, _tidy(chunks))
        for level, title, chunks in parser.sections
        if level > 0 and title
    ]


def load_sections(path: Path, cache_dir: Path) -> list[WikiSection]:
    """Parsed sections, cached on disk by the file's size and mtime (parsing takes a second)."""
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Download it first:\n"
            "  wget https://en.wikibooks.org/wiki/X86_Assembly/Print_Version"
            " -O ./docs/wikibooks_x86.html"
        )
    stat = path.stat()
    key = [str(path), stat.st_size, int(stat.st_mtime)]
    cache = cache_dir / "wikibooks_sections.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data["key"] == key:
            return [WikiSection(**s) for s in data["sections"]]
    sections = parse_sections(path.read_text(encoding="utf-8"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({"key": key, "sections": [asdict(s) for s in sections]}), encoding="utf-8"
    )
    return sections


def find(sections: list[WikiSection], query: str) -> list[WikiSection]:
    """Sections whose title contains every word of the query (case-insensitive)."""
    words = query.lower().split()
    return [s for s in sections if all(w in s.title.lower() for w in words)]


def grep(sections: list[WikiSection], query: str, width: int = 70) -> list[tuple[WikiSection, str]]:
    """(section, snippet) for every section whose body contains the query, one snippet each."""
    needle = query.lower()
    hits = []
    for s in sections:
        i = s.text.lower().find(needle)
        if i >= 0:
            lo, hi = max(0, i - width), min(len(s.text), i + len(query) + width)
            hits.append((s, re.sub(r"\s+", " ", s.text[lo:hi]).strip()))
    return hits
