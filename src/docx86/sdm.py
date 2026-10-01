"""Look up instructions in a local copy of the Intel SDM (authoring aid, not used by the web app).

The SDM PDF has a bookmark outline whose "Instructions (A-L)" / "(M-U)" / "(V)" / "(W-Z)" parents
list every Vol. 2 instruction reference entry as 'MNEMONIC—Description'. We turn that outline into
{title, first_page, last_page} records so an author can jump straight to an instruction's pages
instead of paging through a 5,000-page PDF. Page numbers are 1-based PDF page indexes.

Needs PyMuPDF (`uv sync --group sdm`, installed by default for development).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PARENT_RE = re.compile(r"Instructions \([A-Z]-[A-Z]\)")


@dataclass(frozen=True)
class SdmEntry:
    title: str  # exact outline title, e.g. 'ADD—Add'
    first_page: int
    last_page: int

    @property
    def mnemonics(self) -> list[str]:
        """'CMPXCHG8B/CMPXCHG16B—Compare...' -> ['CMPXCHG8B', 'CMPXCHG16B']."""
        head = re.split(r"\s*[—,]\s*", self.title, maxsplit=1)[0]
        return [m for m in re.split(r"[/ ]+", head) if m]


def _open(pdf: Path):
    try:
        import pymupdf
    except ImportError as err:  # pragma: no cover
        raise SystemExit("PyMuPDF missing: run `uv sync --group sdm`") from err
    if not pdf.exists():
        raise SystemExit(
            f"{pdf} not found. Download it first (see README 'Development'): "
            "wget https://cdrdv2-public.intel.com/929349/325462-093-sdm-vol-1-2abcd-3abcd-4.pdf "
            "-O docs/docs.x86.pdf"
        )
    return pymupdf.open(pdf)


def load_entries(pdf: Path, cache_dir: Path) -> list[SdmEntry]:
    """Instruction entries from the PDF outline; cached because opening the PDF takes seconds."""
    stat = pdf.stat() if pdf.exists() else None
    cache = cache_dir / "sdm_entries.json"
    key = [str(pdf), stat.st_size if stat else 0]
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data["key"] == key:
            return [SdmEntry(**e) for e in data["entries"]]

    doc = _open(pdf)
    toc = doc.get_toc()
    entries: list[SdmEntry] = []
    parent = ""
    for i, (level, title, page) in enumerate(toc):
        if level == 3:
            parent = title
        if level == 4 and "—" in title and PARENT_RE.search(parent):
            nxt = next((p for lv, _, p in toc[i + 1 :] if lv <= 4), page + 1)
            entries.append(SdmEntry(title, page, max(page, nxt - 1)))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({"key": key, "entries": [asdict(e) for e in entries]}), encoding="utf-8"
    )
    return entries


def is_exact(entry: SdmEntry, query: str) -> bool:
    return query.strip().lower() in (m.lower() for m in entry.mnemonics)


def find(entries: list[SdmEntry], query: str) -> list[SdmEntry]:
    """Entries whose mnemonic list matches exactly (page order), else title substring matches."""
    exact = [e for e in entries if is_exact(e, query)]
    return exact or [e for e in entries if query.strip().lower() in e.title.lower()]


def read_pages(pdf: Path, first: int, last: int) -> str:
    doc = _open(pdf)
    return "\n".join(f"##### PDF page {p}\n{doc[p - 1].get_text()}" for p in range(first, last + 1))
