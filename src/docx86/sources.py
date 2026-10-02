"""Read the reference documents into citable units (sentences, table rows, code).

The evidence ledger points at a unit of a source by (document, page or section, fingerprint). This
module turns a document into those units, identically every time, so a pointer recorded today
resolves tomorrow, and a changed document makes it fail loudly.

Documents are the user's own local copies (see README, "Development"): they are git-ignored and are
never shipped in the container image, so a deployment cannot show their text. Anything that needs
the text (the highlighted evidence view, `docx86 evidence cite|suggest|show`, source checks) works
only where the files exist; everything else (coverage, citations) works from the ledger alone.

Kinds of source:
  PdfSource   the Intel SDM and the System V ABI. Pages are split into blocks; the SDM's opcode
              tables become rows; headings ("Description", "Flags Affected", ...) label the parts.
  HtmlSource  the Wikibooks book and Microsoft Learn pages, split by their headings.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .textunits import SPLITTER_VERSION, digest, split_sentences, tidy

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class Unit:
    id: str  # fingerprint of the wording
    text: str  # readable text
    kind: str  # "sentence" | "row" | "code"
    page: int | None  # PDF page where the unit starts
    part: str  # "Description", "Flags Affected", "Opcode table", a heading, ...
    para: int  # index of the containing paragraph (unique within one extraction)


@dataclass
class Paragraph:
    index: int
    part: str
    page: int | None
    units: list[Unit] = field(default_factory=list)
    header: tuple[str, ...] = ()  # column names when the units are table rows


@dataclass(frozen=True)
class Located:
    paragraph: Paragraph
    unit: Unit


# ----------------------------------------------------------------------------------------------
# PDF layout helpers
# ----------------------------------------------------------------------------------------------

# Section headings inside an SDM instruction entry.
SDM_HEADINGS = {
    "Description", "Operation", "Flags Affected", "Instruction Operand Encoding",
    "Intel C/C++ Compiler Intrinsic Equivalent", "IA-32 Architecture Compatibility",
    "Protected Mode Exceptions", "Real-Address Mode Exceptions", "Virtual-8086 Mode Exceptions",
    "Compatibility Mode Exceptions", "64-Bit Mode Exceptions", "Numeric Exceptions",
    "SIMD Floating-Point Exceptions", "Other Exceptions", "Exceptions (All Operating Modes)",
}  # fmt: skip
_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+){1,5}\s+\S.{2,100}$")
_RUNNING_FOOTER = re.compile(r"^(.{0,90}\s)?(\d+-\d+\s+)?Vol\.\s*\d[A-D]?(\s+\d+-\d+)?$")
_SDM_PAGE_FOOTER = re.compile(r"^\d+-\d+\s+Vol\.\s*\d[A-D]?$")
_PSABI_FOOTER = re.compile(
    r"^AMD64 ABI Draft .*$|^\d+\s+AMD64 ABI Draft .*$|^.*AMD64 ABI Draft [\d.]+ .*$"
)
_BULLET_ONLY = re.compile(r"^[•●▪\-–]$")
_TERMINAL = re.compile(r"[.!?:;)\]\"']$")


def _is_noise(text: str, y0: float, y1: float, height: float) -> bool:
    """Running headers and footers."""
    t = tidy(text)
    if _RUNNING_FOOTER.match(t) or _SDM_PAGE_FOOTER.match(t) or _PSABI_FOOTER.match(t):
        return True
    if re.fullmatch(r"\d{1,4}", t) and y0 > 0.85 * height:
        return True  # a bare page number (the System V ABI puts it above its footer line)
    in_edge = y0 < 0.115 * height or y1 > 0.935 * height
    short = len(t) <= 110 and not t.endswith(".")
    if in_edge and short and (t.isupper() or re.fullmatch(r"\d{1,4}", t)):
        return True  # chapter-title header in capitals, bare page number
    return in_edge and y0 < 0.115 * height and bool(re.match(r"^[^.]{2,90}—[^.]{2,120}$", t))


def _is_entry_header(text: str, y0: float, height: float) -> bool:
    """The running title that appears only on the first page of an SDM instruction entry."""
    t = tidy(text)
    return y0 < 0.115 * height and bool(re.match(r"^[^.]{2,90}\u2014[^.]{2,120}$", t))


def _is_heading(text: str, headings: set[str]) -> bool:
    t = tidy(text)
    if t in headings or (t.endswith("Exceptions") and len(t) < 60):
        return True
    return bool(_NUMBERED_HEADING.match(t)) and not t.endswith(".") and len(t) < 110


def _repair_hyphens(text: str, vocab: set[str]) -> str:
    """Rejoin words the typesetter broke with 'hyphen space' (instruc- tion), keep real hyphens."""

    def fix(m: re.Match[str]) -> str:
        joined = m.group(1) + m.group(2)
        return joined if joined.lower() in vocab else f"{m.group(1)}-{m.group(2)}"

    return re.sub(r"([A-Za-z]{2,})- ([a-z]{2,})", fix, text)


# The SDM marks 8-bit operands with a superscript footnote number ("r/m8¹"); extraction turns it
# into a digit ("r/m81"). Showing it as "r/m8[1]" does not change the fingerprint.
_FOOTNOTE_MARK = re.compile(r"\b(r/m8|r8)([1-9])\b")
_FOOTNOTE_NUMBER = re.compile(r"(?<![\w.])(\d)\.\s+(?=[A-Z])")


def _prepare_prose(text: str) -> str:
    """'NOTES: 1. See ... 2. With ...' becomes 'NOTES: [1] See ... [2] With ...'."""
    if text.lstrip().startswith("NOTES:"):
        return _FOOTNOTE_NUMBER.sub(r"[\1] ", text)
    return text


def _vocabulary(texts: list[str]) -> set[str]:
    words: set[str] = set()
    for t in texts:
        words.update(w.lower() for w in re.findall(r"[A-Za-z]{4,}", t))
    return words


# ----------------------------------------------------------------------------------------------
# Sources
# ----------------------------------------------------------------------------------------------


class Source:
    """A reference document. Subclasses implement `_build` for a locator (page or section)."""

    id: str
    label: str  # shown in the UI: "Intel SDM (325462-093)"
    download: str  # how to obtain the local copy

    def __init__(
        self, id: str, label: str, path: Path, download: str, cache_dir: Path | None = None
    ):
        self.id, self.label, self.path, self.download = id, label, path, download
        self._cache_dir = cache_dir
        self._memo: dict[object, list[Paragraph]] = {}
        self._lock = threading.RLock()

    # -- to override --------------------------------------------------------------------------
    def _build(self, locator: object) -> list[Paragraph]:
        raise NotImplementedError

    # -- public -------------------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self.path.exists()

    def paragraphs(self, locator: int | str) -> list[Paragraph]:
        """The paragraphs of one page (PDF) or section (HTML). Empty if the source is missing."""
        if not self.available:
            return []
        with self._lock:
            if locator not in self._memo:
                self._memo[locator] = self._load_or_build(locator)
            return self._memo[locator]

    def units(self, locator: int | str) -> Iterator[Located]:
        for para in self.paragraphs(locator):
            for unit in para.units:
                yield Located(para, unit)

    def find(self, locator: int | str, unit_id: str) -> Located | None:
        return next((loc for loc in self.units(locator) if loc.unit.id == unit_id), None)

    def search(self, locator: int | str, needle: str) -> list[Located]:
        n = needle.lower()
        return [loc for loc in self.units(locator) if n in loc.unit.text.lower()]

    # -- on-disk cache (extraction is slow for PDFs) ---------------------------------------------
    def _cache_file(self, locator: object) -> Path | None:
        if self._cache_dir is None:
            return None
        st = self.path.stat()
        key = f"{self.id}-{st.st_size}-{int(st.st_mtime)}-v{SPLITTER_VERSION}-{locator}"
        return self._cache_dir / "units" / (re.sub(r"[^A-Za-z0-9._-]+", "_", key) + ".json")

    def _load_or_build(self, locator: object) -> list[Paragraph]:
        cache = self._cache_file(locator)
        if cache and cache.exists():
            try:
                return _paragraphs_from_json(json.loads(cache.read_text(encoding="utf-8")))
            except (ValueError, KeyError, TypeError):
                pass
        built = self._build(locator)
        if cache:
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps([asdict(p) for p in built]), encoding="utf-8")
            except OSError:
                pass  # read-only checkout or container: just slower next time
        return built


def _paragraphs_from_json(data: list[dict]) -> list[Paragraph]:
    out = []
    for d in data:
        units = [Unit(**u) for u in d.pop("units")]
        d["header"] = tuple(d.get("header") or ())
        out.append(Paragraph(units=units, **d))
    return out


class PdfSource(Source):
    """A PDF read with PyMuPDF (the `sdm` dependency group; not in the container image)."""

    def __init__(
        self, *args: object, use_tables: bool = False, headings: set[str] | None = None, **kw
    ):
        super().__init__(*args, **kw)  # type: ignore[arg-type]
        self.use_tables = use_tables
        self.headings = headings or set()
        self._doc = None
        self._blocks: dict[int, tuple[list[tuple[float, float, float, float, str]], bool]] = {}

    def _open(self):
        if self._doc is None:
            import pymupdf  # imported lazily: absent from the production image

            self._doc = pymupdf.open(self.path)
        return self._doc

    @property
    def available(self) -> bool:
        if not self.path.exists():
            return False
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            return False
        return True

    def page_count(self) -> int:
        with self._lock:
            return self._open().page_count

    def toc(self) -> list[tuple[int, str, int]]:
        with self._lock:
            return [(lv, t, p) for lv, t, p in self._open().get_toc()]

    # -- extraction ------------------------------------------------------------------------------
    def _raw_blocks(self, number: int) -> tuple[list[tuple[float, float, float, float, str]], bool]:
        """Text blocks of a page without running headers/footers, and whether it starts an entry."""
        cached = self._blocks.get(number)
        if cached is not None:
            return cached
        page = self._open()[number - 1]
        height = page.rect.height
        kept, starts_entry = [], False
        for x0, y0, x1, y1, text, _no, typ in page.get_text("blocks"):
            if typ != 0 or not text.strip():
                continue
            if _is_noise(text, y0, y1, height):
                starts_entry = starts_entry or _is_entry_header(text, y0, height)
                continue
            kept.append((x0, y0, x1, y1, text))
        self._blocks[number] = (kept, starts_entry)
        return self._blocks[number]

    def _page_items(self, number: int) -> list[tuple[float, str, object]]:
        """('block'|'table', payload) in reading order for one page."""
        page = self._open()[number - 1]
        tables = list(page.find_tables().tables) if self.use_tables else []
        items: list[tuple[float, str, object]] = []
        for t in tables:
            rows = [[tidy(c or "") for c in row] for row in t.extract()]
            rows = [r for r in rows if any(r)]
            if rows:
                items.append((t.bbox[1], "table", rows))
        for x0, y0, x1, y1, text in self._raw_blocks(number)[0]:
            inside = any(
                t.bbox[0] - 2 <= x0
                and x1 <= t.bbox[2] + 2
                and t.bbox[1] - 2 <= y0
                and y1 <= t.bbox[3] + 2
                for t in tables
            )
            if not inside:
                items.append((y0, "block", text))
        items.sort(key=lambda it: it[0])
        return items

    def _last_heading(self, number: int) -> str | None:
        for _x0, _y0, _x1, _y1, text in reversed(self._raw_blocks(number)[0]):
            if _is_heading(text, self.headings):
                return tidy(text)
        return None

    def _initial_part(self, page: int) -> str:
        """The heading in force at the top of a page: the last one seen on the pages before it."""
        if self._raw_blocks(page)[1]:  # first page of an entry: nothing carries over
            return ""
        for p in range(page - 1, max(0, page - 9), -1):
            heading = self._last_heading(p)
            if heading:
                return heading
            if self._raw_blocks(p)[1]:
                break
        return self._toc_part(page)

    def _continues_previous_page(self, page: int) -> bool:
        """True if this page's first prose block continues a paragraph from the previous page."""
        if page <= 1 or self._raw_blocks(page)[1]:
            return False
        blocks = [b for b in self._raw_blocks(page)[0] if not _is_heading(b[4], self.headings)]
        previous = self._raw_blocks(page - 1)[0]
        if not blocks or not previous or not tidy(blocks[0][4])[:1].islower():
            return False
        return not _TERMINAL.search(tidy(previous[-1][4]))

    def _build(self, page_number: object) -> list[Paragraph]:
        assert isinstance(page_number, int)
        with self._lock:
            last = min(page_number + 1, self._open().page_count)
            raw: list[tuple[int, str, object]] = []  # (page, kind, payload)
            for p in range(page_number, last + 1):
                raw += [(p, kind, payload) for _y, kind, payload in self._page_items(p)]
            if raw and raw[0][1] == "block" and self._continues_previous_page(page_number):
                raw = raw[1:]  # belongs to the paragraph that started on the previous page
            vocab = _vocabulary([str(pl) for _p, k, pl in raw if k == "block"])
            initial = self._initial_part(page_number)
        paragraphs = self._paragraphs(raw, vocab, initial)
        return [p for p in paragraphs if p.page == page_number]  # sentences that START on this page

    def _toc_part(self, page: int) -> str:
        best = ""
        for _lv, title, p in self.toc():
            if p <= page:
                best = title
        return best

    def _paragraphs(
        self, raw: list[tuple[int, str, object]], vocab: set[str], part: str
    ) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        pending: tuple[int, str, str] | None = None  # (page, part, text) of an unfinished paragraph

        def flush(prose: tuple[int, str, str] | None) -> None:
            if not prose:
                return
            page, prt, text = prose
            text = _prepare_prose(_repair_hyphens(tidy(text), vocab))
            if prt == "Operation":
                units = [Unit(digest(text), text, "code", page, prt, len(paragraphs))]
            else:
                units = [
                    Unit(
                        digest(s),
                        s.lstrip("\u2022\u25cf ").strip(),
                        "sentence",
                        page,
                        prt,
                        len(paragraphs),
                    )
                    for s in split_sentences(text)
                ]
            if units:
                paragraphs.append(Paragraph(len(paragraphs), prt, page, units))

        for page, kind, payload in raw:
            if kind == "table":
                flush(pending)
                pending = None
                rows: list[list[str]] = payload  # type: ignore[assignment]
                is_header = lambda r: any(c.startswith(("Opcode", "Op/En", "Op/ En")) for c in r)  # noqa: E731
                header = tuple(c for c in rows[0] if c) if is_header(rows[0]) else ()
                body = rows[1:] if header else rows
                if header:  # an SDM opcode / operand-encoding table: its footnotes belong to it
                    label = (
                        "Operand encoding"
                        if any("Operand 1" in c for c in header)
                        else "Opcode table"
                    )
                    part = label
                else:
                    label = "Table"
                units = []
                for r in body:
                    text = " | ".join(_repair_hyphens(c, vocab) for c in r if c)
                    text = _FOOTNOTE_MARK.sub(r"\1[\2]", text)
                    units.append(Unit(digest(text), text, "row", page, label, len(paragraphs)))
                if units:
                    paragraphs.append(Paragraph(len(paragraphs), label, page, units, header))
                continue
            text = str(payload)
            t = tidy(text)
            if _BULLET_ONLY.match(t):
                continue
            if _is_heading(text, self.headings):
                flush(pending)
                pending = None
                part = t
                continue
            if pending and not _TERMINAL.search(pending[2].rstrip()) and t[:1].islower():
                pending = (pending[0], pending[1], pending[2] + " " + text)  # paragraph continues
                continue
            flush(pending)
            pending = (page, part, text)
        flush(pending)
        return paragraphs


class HtmlSource(Source):
    """A saved web page split into sections by its h1-h4 headings."""

    def _sections(self) -> dict[str, str]:
        from .wikibooks import parse_sections

        with self._lock:
            if not hasattr(self, "_parsed"):
                self._parsed = parse_sections(self.path.read_text(encoding="utf-8"))
            result: dict[str, str] = {}
            for s in self._parsed:
                result.setdefault(s.title, s.text)
            return result

    def section_titles(self) -> list[str]:
        return list(self._sections())

    def _build(self, section: object) -> list[Paragraph]:
        text = self._sections().get(str(section))
        if text is None:
            return []
        paragraphs: list[Paragraph] = []
        vocab = _vocabulary([text])
        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if not block:
                continue
            body = _repair_hyphens(tidy(block), vocab)
            sentences = split_sentences(body)
            units = [
                Unit(digest(s), s, "sentence", None, str(section), len(paragraphs))
                for s in sentences
            ]
            if units:
                paragraphs.append(Paragraph(len(paragraphs), str(section), None, units))
        return paragraphs


# ----------------------------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------------------------

SDM_DOWNLOAD = (
    "wget https://cdrdv2-public.intel.com/929349/325462-093-sdm-vol-1-2abcd-3abcd-4.pdf "
    "-O ./docs/docs.x86.pdf"
)
SYSV_DOWNLOAD = "wget https://refspecs.linuxbase.org/elf/x86_64-abi-0.99.pdf -O ./docs/sysv_abi.pdf"
MS_CONV_DOWNLOAD = (
    "wget https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention "
    "-O ./docs/ms_x64_calling_convention.html"
)
MS_STACK_DOWNLOAD = (
    "wget https://learn.microsoft.com/en-us/cpp/build/stack-usage -O ./docs/ms_x64_stack_usage.html"
)
WIKI_DOWNLOAD = (
    "wget https://en.wikibooks.org/wiki/X86_Assembly/Print_Version -O ./docs/wikibooks_x86.html"
)

# Ledger `src` values that point into a document (as opposed to `run` and `derived`).
DOCUMENT_SOURCES = ("sdm", "sysv", "msx64", "msstack", "wikibooks")


class SourceRegistry:
    def __init__(self, settings: Settings, cache_dir: Path | None = None):
        c = cache_dir
        self._sources: dict[str, Source] = {
            "sdm": PdfSource(
                "sdm",
                "Intel SDM, order no. 325462-093",
                settings.sdm_pdf,
                SDM_DOWNLOAD,
                c,
                use_tables=True,
                headings=SDM_HEADINGS,
            ),
            "sysv": PdfSource(
                "sysv",
                "System V AMD64 ABI, draft 0.99.6",
                settings.sysv_abi_pdf,
                SYSV_DOWNLOAD,
                c,
            ),
            "msx64": HtmlSource(
                "msx64",
                "Microsoft Learn: x64 Calling Convention",
                settings.ms_calling_convention_html,
                MS_CONV_DOWNLOAD,
                c,
            ),
            "msstack": HtmlSource(
                "msstack",
                "Microsoft Learn: x64 stack usage",
                settings.ms_stack_usage_html,
                MS_STACK_DOWNLOAD,
                c,
            ),
            "wikibooks": HtmlSource(
                "wikibooks",
                "Wikibooks: x86 Assembly (CC BY-SA)",
                settings.wikibooks_html,
                WIKI_DOWNLOAD,
                c,
            ),
        }

    def __getitem__(self, src: str) -> Source:
        return self._sources[src]

    def __contains__(self, src: str) -> bool:
        return src in self._sources

    def all(self) -> list[Source]:
        return list(self._sources.values())
