"""The evidence ledger: which sentence of which reference document supports which claim.

`claims.py` breaks a page into claims; this module records, per page, where each claim comes from
and reports how much of the page is covered. The ledger is a sidecar file,
`content/evidence/<instructions|articles>/<slug>.yaml`, so pages stay exactly as they are written.

What a ledger holds (see docs/EVIDENCE.md for the full story):

  * pointers: (document, page or section, fingerprint of the sentence), plus a short attributed
    quotation of each cited sentence (`quotes`, at most MAX_QUOTE characters, never pseudocode), so
    the page can show the very sentence a claim rests on without anyone's copy of the document. The
    surrounding text is rendered only from a copy of the document on the reader's machine;
  * claims are identified by the fingerprint of their wording, so editing a sentence orphans its
    evidence and `check` says so, instead of letting a stale citation vouch for new words;
  * a quote is checked against its own fingerprint, so a quote cannot drift from, or be swapped for,
    the sentence it claims to be;
  * who made each link (`by`): `auto` (a similarity suggestion, unconfirmed), `match` (an exact
    mechanical match, such as the same opcode and syntax in an SDM table row), `llm` or `human`.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml
from markupsafe import Markup, escape
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .claims import Claim, claims_for_article, claims_for_instruction
from .sources import DOCUMENT_SOURCES, Located, Source, SourceRegistry
from .textunits import SPLITTER_VERSION, digest

if TYPE_CHECKING:
    from .content import Content

Doc = Literal["sdm", "sysv", "msx64", "msstack", "wikibooks"]
By = Literal["auto", "match", "llm", "human"]
How = Literal["source", "derived", "run", "illustrative", "editorial", "external"]

# Coverage states, strongest first. GROUNDED claims rest on sentences of a document; ILLUSTRATIVE
# and EDITORIAL ones are examples and advice that no document states; "external" is cited to
# something we cannot look sentences up in; "suggested" and "unverified" are still open.
STATES = (
    "traced",
    "derived",
    "run",
    "illustrative",
    "editorial",
    "external",
    "suggested",
    "unverified",
)
GROUNDED = ("traced", "derived", "run")
OPEN = ("suggested", "unverified")
STATE_LABELS = {
    "traced": "Traced to a source",
    "derived": "Derived from sources",
    "run": "Checked by running it",
    "illustrative": "Illustrative example",
    "editorial": "Advice or editorial",
    "external": "Cited to an outside source",
    "suggested": "Suggested match (unconfirmed)",
    "unverified": "Not yet checked",
}
KINDS = {"instruction": "instructions", "article": "articles"}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Support(_Model):
    """A pointer into one place of one document."""

    doc: Doc
    at: int | str = Field(description="PDF page where the sentence starts, or HTML section title.")
    units: list[str] = Field(min_length=1, description="Fingerprints of the cited sentences/rows.")
    part: str | None = Field(default=None, description="Display hint: 'Description', 'Table'.")
    by: By = "llm"
    note: str | None = None
    quotes: dict[str, str] = Field(
        default_factory=dict,
        description="The cited sentences themselves, by fingerprint (see MAX_QUOTE).",
    )

    @model_validator(mode="after")
    def _quotes_are_of_cited_units(self) -> Support:
        stray = set(self.quotes) - set(self.units)
        if stray:
            raise ValueError(f"quotes for sentences that are not cited: {sorted(stray)}")
        return self


# Quotation, not reproduction: one sentence or table row at a time, kept short, with its source.
# Pseudocode blocks and run-on table extractions are cited by pointer only.
MAX_QUOTE = 400
QUOTABLE_KINDS = ("sentence", "row")
ROW_PARTS = ("Opcode table", "Operand encoding", "Table")


def quotable(unit) -> bool:
    """Whether a source unit may be quoted in the ledger."""
    return unit.kind in QUOTABLE_KINDS and len(unit.text) <= MAX_QUOTE


class Entry(_Model):
    id: str = Field(description="Fingerprint of the claim's wording (see claims.py).")
    gist: str | None = Field(
        default=None, description="Start of the claim, for people reading YAML."
    )
    how: How = "source"
    support: list[Support] = Field(default_factory=list)
    ref: str | None = Field(
        default=None, description="`run`: repo path of the program that checks it."
    )
    note: str | None = None
    by: By = "llm"  # who classified a non-source entry


class Ledger(_Model):
    splitter: int = SPLITTER_VERSION
    claims: list[Entry] = Field(default_factory=list)


def state_of(entry: Entry | None) -> str:
    if entry is None:
        return "unverified"
    if entry.how != "source":
        return entry.how
    return "traced" if any(s.by != "auto" for s in entry.support) else "suggested"


# ----------------------------------------------------------------------------------------------
# Pages and the store
# ----------------------------------------------------------------------------------------------


@dataclass
class ClaimView:
    claim: Claim
    entry: Entry | None

    @property
    def state(self) -> str:
        return state_of(self.entry)


@dataclass
class PageEvidence:
    kind: str  # "instruction" | "article"
    slug: str
    title: str
    status: str  # "draft" | "reviewed"
    claims: list[ClaimView]
    path: Path  # where the ledger lives (whether or not it exists yet)
    ledger_exists: bool = False
    stale: list[Entry] = field(default_factory=list)  # entries whose claim no longer exists
    load_problems: list[str] = field(default_factory=list)
    splitter: int = SPLITTER_VERSION
    extra_ids: list[str] = field(default_factory=list)  # duplicate ids in the file

    @property
    def url(self) -> str:
        return f"/{KINDS[self.kind]}/{self.slug}/evidence"

    @property
    def page_url(self) -> str:
        return f"/{KINDS[self.kind]}/{self.slug}"

    def counts(self) -> dict[str, int]:
        c = Counter(v.state for v in self.claims)
        return {s: c.get(s, 0) for s in STATES}

    @property
    def total(self) -> int:
        return len(self.claims)

    @property
    def grounded(self) -> int:
        """Statements that rest on a sentence of a document (or on a program that was run)."""
        counts = self.counts()
        return sum(counts[s] for s in GROUNDED)

    @property
    def open(self) -> int:
        counts = self.counts()
        return sum(counts[s] for s in OPEN)

    @property
    def percent_grounded(self) -> int:
        return round(100 * self.grounded / self.total) if self.total else 100

    def view(self, claim_id: str) -> ClaimView | None:
        return next((v for v in self.claims if v.claim.id == claim_id), None)

    def selector(self, ref: str) -> ClaimView:
        """A claim by id, unique id prefix or 1-based position (as `evidence show` lists them)."""
        if ref.isdigit() and 1 <= int(ref) <= len(self.claims) and len(ref) < 5:
            return self.claims[int(ref) - 1]
        hits = [v for v in self.claims if v.claim.id.startswith(ref.lower())]
        if len(hits) != 1:
            raise KeyError(f"{ref!r} matches {len(hits)} claims of {self.slug}")
        return hits[0]


def ledger_path(evidence_dir: Path, kind: str, slug: str) -> Path:
    return evidence_dir / KINDS[kind] / f"{slug}.yaml"


def read_ledger(path: Path) -> Ledger:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Ledger.model_validate(data)


class _Flow(dict):
    """Rendered on one line in the YAML file ({doc: sdm, at: 1234, ...}); keeps diffs small."""


class _FlowList(list):
    """A list rendered as [a, b]."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(
    _Flow, lambda d, data: d.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)
)
_Dumper.add_representer(
    _FlowList, lambda d, data: d.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)
)
_Dumper.add_representer(
    str,
    lambda d, data: d.represent_scalar(
        "tag:yaml.org,2002:str", data, style="|" if "\n" in data else None
    ),
)

HEADER = (
    "# Evidence ledger: which sentence of which document supports which claim of this page.\n"
    "# Pointers (document, page or section, fingerprint) with a short quotation of each cited\n"
    "# sentence. Managed by `docx86 evidence ...`; see docs/EVIDENCE.md before editing by hand.\n"
)


def _support_dict(s: Support) -> dict:
    data = s.model_dump(exclude_defaults=True, exclude_none=True)
    if not s.note and not s.quotes:
        return _Flow(data)  # one line per bare pointer; notes and quotes make it a block
    data["units"] = _FlowList(data["units"])
    return data


def _dump_entry(e: Entry) -> dict:
    out: dict = {"id": e.id}
    if e.gist:
        out["gist"] = e.gist
    if e.how != "source":
        out["how"] = e.how
        if e.by != "llm":
            out["by"] = e.by
    if e.ref:
        out["ref"] = e.ref
    if e.note:
        out["note"] = e.note
    if e.support:
        out["support"] = [_support_dict(s) for s in e.support]
    return out


def dump_ledger(ledger: Ledger) -> str:
    body = {"splitter": ledger.splitter, "claims": [_dump_entry(e) for e in ledger.claims]}
    return HEADER + yaml.dump(
        body,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
        default_flow_style=False,
    )


def gist_of(text: str, limit: int = 64) -> str:
    plain = re.sub(r"\s+", " ", plain_text(text)).strip()
    return plain if len(plain) <= limit else plain[: limit - 1].rstrip() + "…"


def plain_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)  # _emphasis_, but not __builtin_x
    return re.sub(r"[`*]", "", text)


class EvidenceStore:
    """Every page's claims joined with its ledger. Built once; cheap (no source documents read)."""

    def __init__(self, content: Content, evidence_dir: Path):
        self.dir = Path(evidence_dir)
        self._pages: dict[tuple[str, str], PageEvidence] = {}
        for ins in content.instructions.values():
            self._add(
                "instruction", ins.slug, ins.title, ins.status.value, claims_for_instruction(ins)
            )
        for art in content.articles.values():
            self._add("article", art.slug, art.title, art.status.value, claims_for_article(art))

    def _add(self, kind: str, slug: str, title: str, status: str, claims: list[Claim]) -> None:
        path = ledger_path(self.dir, kind, slug)
        page = PageEvidence(kind, slug, title, status, [], path)
        entries: dict[str, Entry] = {}
        if path.exists():
            page.ledger_exists = True
            try:
                ledger = read_ledger(path)
            except (ValidationError, yaml.YAMLError) as err:
                page.load_problems.append(f"{path}: {str(err).splitlines()[0]}")
                ledger = Ledger()
            page.splitter = ledger.splitter
            for e in ledger.claims:
                if e.id in entries:
                    page.extra_ids.append(e.id)
                entries[e.id] = e
        current = {c.id for c in claims}
        page.claims = [ClaimView(c, entries.get(c.id)) for c in claims]
        page.stale = [e for e in entries.values() if e.id not in current]
        self._pages[(kind, slug)] = page

    def get(self, kind: str, slug: str) -> PageEvidence | None:
        return self._pages.get((kind, slug))

    def pages(self, kind: str | None = None) -> list[PageEvidence]:
        return [p for (k, _), p in self._pages.items() if kind in (None, k)]

    def orphan_files(self) -> list[Path]:
        """Ledger files with no page behind them."""
        known = {p.path.resolve() for p in self._pages.values()}
        found = [f for sub in KINDS.values() for f in sorted((self.dir / sub).glob("*.yaml"))]
        return [f for f in found if f.resolve() not in known]

    def totals(self) -> dict[str, int]:
        c: Counter[str] = Counter()
        for p in self._pages.values():
            c.update(p.counts())
        return {s: c.get(s, 0) for s in STATES}


# ----------------------------------------------------------------------------------------------
# Recording evidence
# ----------------------------------------------------------------------------------------------


def _merge(old: Entry | None, new: Entry) -> Entry:
    """Combine a new link with what is already recorded for the claim."""
    if old is None:
        return new
    if new.how != "source" or old.how != "source":
        # Classifying a claim keeps the confirmed links it already had, and drops the guesses.
        confirmed = [s for s in old.support if s.by != "auto"]
        return new.model_copy(update={"support": confirmed + new.support})
    if new.support and all(s.by == "auto" for s in new.support):
        # A fresh suggestion replaces the earlier guesses, and never touches confirmed links.
        kept = [s for s in old.support if s.by != "auto"]
        return old.model_copy(update={"support": kept + new.support})
    rank = {"auto": 0, "match": 1, "llm": 2, "human": 3}
    # A confirmed link supersedes the guesses; without one, the guesses stay as they were.
    confirmed = any(s.by != "auto" for s in new.support)
    supports = [s for s in old.support if s.by != "auto"] if confirmed else list(old.support)
    for s in new.support:
        same = next((i for i, o in enumerate(supports) if (o.doc, o.at) == (s.doc, s.at)), None)
        if same is None:
            supports.append(s)
            continue
        o = supports[same]
        units = o.units + [u for u in s.units if u not in o.units]
        by = s.by if rank[s.by] >= rank[o.by] else o.by
        quotes = {u: q for u, q in {**o.quotes, **s.quotes}.items() if u in units}
        supports[same] = o.model_copy(
            update={
                "units": units,
                "by": by,
                "note": s.note or o.note,
                "part": s.part or o.part,
                "quotes": quotes,
            }
        )
    return old.model_copy(update={"support": supports, "note": new.note or old.note})


def record(page: PageEvidence, entries: list[Entry]) -> Ledger:
    """The page's ledger with `entries` merged in, in the order the claims appear on the page."""
    by_id = {v.claim.id: v.entry for v in page.claims if v.entry}
    for e in entries:
        if e.gist is None:
            view = page.view(e.id)
            e = e.model_copy(update={"gist": gist_of(view.claim.text) if view else None})
        by_id[e.id] = _merge(by_id.get(e.id), e)
    order = {v.claim.id: i for i, v in enumerate(page.claims)}
    kept = sorted(by_id.values(), key=lambda e: order.get(e.id, len(order)))
    return Ledger(splitter=SPLITTER_VERSION, claims=kept)


def quotes_for(support: Support, registry: SourceRegistry | None, *, refresh: bool = False) -> dict:
    """The quotes `support` should carry, taken from the local document (empty if it is absent)."""
    source = registry[support.doc] if registry else None
    if source is None or not source.available:
        return dict(support.quotes)
    found = {}
    for loc in source.units(support.at):
        if loc.unit.id in support.units and quotable(loc.unit):
            found.setdefault(loc.unit.id, loc.unit.text)
    kept = {} if refresh else dict(support.quotes)
    return {u: kept.get(u) or found[u] for u in support.units if u in found or u in kept}


def attach_quotes(
    page: PageEvidence, registry: SourceRegistry | None, *, refresh: bool = False
) -> tuple[Ledger, int]:
    """The page's ledger with a quote on every pointer whose sentence is quotable and known.

    Returns the ledger and how many quotes were added or changed. Needs the local documents.
    """
    changed = 0
    entries = []
    for v in page.claims:
        if v.entry is None:
            continue
        supports = []
        for s in v.entry.support:
            quotes = quotes_for(s, registry, refresh=refresh)
            changed += sum(1 for u, q in quotes.items() if s.quotes.get(u) != q)
            supports.append(s.model_copy(update={"quotes": quotes}))
        entries.append(v.entry.model_copy(update={"support": supports}))
    kept = {e.id for e in entries}
    entries += [e for e in page.stale if e.id not in kept]
    return Ledger(splitter=page.splitter, claims=entries), changed


def save(page: PageEvidence, ledger: Ledger) -> None:
    page.path.parent.mkdir(parents=True, exist_ok=True)
    page.path.write_text(dump_ledger(ledger), encoding="utf-8")


# ----------------------------------------------------------------------------------------------
# Checking
# ----------------------------------------------------------------------------------------------


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    resolved: int = 0  # pointers confirmed against a local document
    unchecked: int = 0  # pointers that could not be looked up here (document missing)
    quotes_ok: int = 0  # stored quotes whose fingerprint matches the sentence they cite


def _closest(page: PageEvidence, entry: Entry) -> str:
    if not entry.gist:
        return ""
    best = max(
        page.claims,
        key=lambda v: difflib.SequenceMatcher(
            None, entry.gist or "", gist_of(v.claim.text)
        ).ratio(),
        default=None,
    )
    if best is None:
        return ""
    ratio = difflib.SequenceMatcher(None, entry.gist, gist_of(best.claim.text)).ratio()
    return (
        f" (closest current claim: {best.claim.id} {gist_of(best.claim.text)!r})"
        if ratio > 0.5
        else ""
    )


def check_page(
    page: PageEvidence, rep: Report, registry: SourceRegistry | None, root: Path | None
) -> None:
    where = page.path.relative_to(root) if root and page.path.is_relative_to(root) else page.path
    rep.problems += page.load_problems
    if page.load_problems:
        return
    if page.ledger_exists and page.splitter != SPLITTER_VERSION:
        rep.problems.append(
            f"{where}: made with sentence splitter v{page.splitter}, code is v{SPLITTER_VERSION}; "
            "claim and source fingerprints may differ: re-check and update `splitter`"
        )
    for dup in page.extra_ids:
        rep.problems.append(f"{where}: claim {dup} is listed more than once")
    for e in page.stale:
        rep.problems.append(
            f"{where}: claim {e.id} ({e.gist!r}) no longer exists on the page: its wording "
            f"changed or it was removed{_closest(page, e)}. Re-read the sources against the new "
            "wording, then `docx86 evidence retarget` it or drop the entry"
        )
    for v in page.claims:
        e = v.entry
        if e is None:
            continue
        label = f"{where}: claim {e.id} ({gist_of(v.claim.text, 40)!r})"
        if e.how == "source" and not e.support:
            rep.problems.append(f"{label}: how=source needs at least one `support`")
        if e.how == "run":
            if not e.ref:
                rep.problems.append(f"{label}: how=run needs `ref` (the program that checks it)")
            elif root is not None and not (root / e.ref).exists():
                rep.problems.append(f"{label}: ref {e.ref!r} does not exist")
        if e.how in ("derived", "external") and not e.note:
            what = "how it follows" if e.how == "derived" else "which source it comes from"
            rep.problems.append(f"{label}: how={e.how} needs a `note` saying {what}")
        for s in e.support:
            _check_support(s, label, rep, registry)
    if page.status == "reviewed":
        counts = page.counts()
        if counts["unverified"] or counts["suggested"]:
            rep.problems.append(
                f"{where}: status is reviewed, but {counts['unverified']} claim(s) are unchecked "
                f"and {counts['suggested']} only have unconfirmed suggestions"
            )


def _check_support(s: Support, label: str, rep: Report, registry: SourceRegistry | None) -> None:
    if s.doc not in DOCUMENT_SOURCES:  # pragma: no cover - the Literal already rejects this
        rep.problems.append(f"{label}: unknown document {s.doc!r}")
        return
    for unit_id, quote in s.quotes.items():
        if len(quote) > MAX_QUOTE:
            rep.problems.append(
                f"{label}: quote of {unit_id} is {len(quote)} characters; "
                f"quotations are limited to {MAX_QUOTE} (cite long passages by pointer only)"
            )
        elif digest(quote) != unit_id:
            rep.problems.append(
                f"{label}: the quote stored for {unit_id} is not that sentence "
                "(its fingerprint differs; re-run `docx86 evidence quote --refresh`)"
            )
        else:
            rep.quotes_ok += 1
    source: Source | None = registry[s.doc] if registry else None
    wants_page = s.doc in ("sdm", "sysv")
    if wants_page != isinstance(s.at, int):
        wanted = "a PDF page number" if wants_page else "a section title"
        rep.problems.append(f"{label}: `at` for {s.doc} must be {wanted}")
        return
    if source is None or not source.available:
        rep.unchecked += len(s.units)
        return
    known = {loc.unit.id for loc in source.units(s.at)}
    for unit in s.units:
        if unit in known:
            rep.resolved += 1
        else:
            rep.problems.append(
                f"{label}: {s.doc} {'page' if wants_page else 'section'} {s.at!r} has no sentence "
                f"{unit} (the document or the splitter changed; look again: `docx86 evidence find`)"
            )


def check(store: EvidenceStore, registry: SourceRegistry | None, root: Path | None) -> Report:
    """Check every ledger. `root` is the repository checkout that `run` refs are relative to;
    None means there is none (the container image build), so refs are not looked up."""
    rep = Report()
    for page in store.pages():
        check_page(page, rep, registry, root)
    for f in store.orphan_files():
        rep.problems.append(f"{f}: there is no page with this slug")
    if registry is not None:
        missing = sorted(
            {s.id for s in registry.all() if not s.available}
            & {
                sup.doc
                for p in store.pages()
                for v in p.claims
                if v.entry
                for sup in v.entry.support
            }
        )
        for doc_id in missing:
            rep.notices.append(
                f"{registry[doc_id].label}: not available here, so its pointers were not looked up "
                f"({registry[doc_id].download})"
            )
    return rep


# ----------------------------------------------------------------------------------------------
# Showing a claim's sources (needs the local documents)
# ----------------------------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*|\d+")
_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "does", "for", "from",
    "has", "have", "if", "in", "into", "is", "it", "its", "not", "of", "on", "or", "so", "than",
    "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "were", "when",
    "where", "which", "while", "will", "with", "would", "you", "your", "also", "any", "all",
    "each", "only", "other", "such", "use", "used", "uses", "using", "may", "must", "should",
    "one", "two",
})  # fmt: skip


def _stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    return w


def key_terms(text: str) -> set[str]:
    """Stems of the words that carry a claim's meaning (not articles, prepositions, ...)."""
    return {
        _stem(w)
        for w in _WORD.findall(plain_text(text))
        if w.lower() not in _STOP and (len(w) >= 3 or w.isdigit())
    }


def emphasise(text: str, terms: set[str]) -> Markup:
    """Escape `text` and wrap the words that also occur in the claim in <b>."""
    out, pos = [], 0
    for m in _WORD.finditer(text):
        out.append(escape(text[pos : m.start()]))
        word = m.group()
        out.append(Markup("<b>{}</b>").format(word) if _stem(word) in terms else escape(word))
        pos = m.end()
    out.append(escape(text[pos:]))
    return Markup("").join(out)


@dataclass(frozen=True)
class UnitView:
    html: Markup  # escaped; the words shared with the claim are wrapped in <b> for cited units
    text: str  # the same, plain
    cited: bool
    kind: str  # "sentence" | "row" | "code" | "gap"


@dataclass(frozen=True)
class PassageView:
    doc: str
    doc_label: str
    at: int | str
    part: str
    by: str
    note: str | None
    where: str  # "PDF page 1234" / "section “Parameter passing”"
    state: str  # "shown" | "quoted" | "unavailable" | "missing"
    download: str
    units: tuple[UnitView, ...] = ()
    header: tuple[str, ...] = ()
    unquoted: int = 0  # cited sentences with no quote (long tables, pseudocode)


CONTEXT_LIMIT = 14  # paragraphs longer than this are cut to a window around the cited units
CONTEXT_RADIUS = 3
CODE_LIMIT = 1600


def _where(doc: str, at: int | str) -> str:
    return f"PDF page {at}" if doc in ("sdm", "sysv") else f"section “{at}”"


def _unit_html(loc_unit, cited: bool, terms: set[str]) -> UnitView:
    text = loc_unit.text
    if loc_unit.kind == "code" and len(text) > CODE_LIMIT:
        text = text[:CODE_LIMIT].rstrip() + " …"
    html = emphasise(text, terms) if cited else escape(text)
    return UnitView(html, text, cited, loc_unit.kind)


def _quote_views(s: Support, terms: set[str]) -> tuple[UnitView, ...]:
    kind = "row" if (s.part or "") in ROW_PARTS else "sentence"
    return tuple(
        UnitView(emphasise(s.quotes[u], terms), s.quotes[u], True, kind)
        for u in s.units
        if u in s.quotes
    )


def passages(entry: Entry, claim: Claim, registry: SourceRegistry | None) -> list[PassageView]:
    """For each pointer, the paragraph it cites with the cited sentences marked."""
    terms = key_terms(claim.text)
    views: list[PassageView] = []
    for s in entry.support:
        source = registry[s.doc] if registry else None
        base = {
            "doc": s.doc,
            "doc_label": source.label if source else s.doc,
            "at": s.at,
            "by": s.by,
            "note": s.note,
            "where": _where(s.doc, s.at),
            "download": source.download if source else "",
        }
        quoted = _quote_views(s, terms)
        if source is None or not source.available:
            state = "quoted" if quoted else "unavailable"
            views.append(
                PassageView(
                    part=s.part or "",
                    state=state,
                    units=quoted,
                    unquoted=len(s.units) - len(quoted),
                    **base,
                )
            )
            continue
        located: list[Located] = [loc for loc in source.units(s.at) if loc.unit.id in s.units]
        if not located:
            views.append(PassageView(part=s.part or "", state="missing", units=quoted, **base))
            continue
        # One block per paragraph that holds a cited unit. The SDM repeats sentences under
        # several headings (the exception lists), so `part` says which occurrence is meant.
        seen: set[int] = set()
        shown_ids: set[str] = set()
        note = base["note"]  # said once per pointer, under its first passage
        located.sort(key=lambda loc: loc.paragraph.part != s.part)
        for loc in located:
            if loc.paragraph.index in seen or loc.unit.id in shown_ids:
                continue
            seen.add(loc.paragraph.index)
            shown_ids.update(u.id for u in loc.paragraph.units if u.id in s.units)
            para = loc.paragraph
            units = para.units
            cited_idx = [i for i, u in enumerate(units) if u.id in s.units]
            lo, hi = 0, len(units)
            if len(units) > CONTEXT_LIMIT:
                lo = max(0, min(cited_idx) - CONTEXT_RADIUS)
                hi = min(len(units), max(cited_idx) + CONTEXT_RADIUS + 1)
            shown: list[UnitView] = []
            if lo > 0:
                shown.append(UnitView(Markup("…"), "…", False, "gap"))
            shown += [_unit_html(units[i], i in cited_idx, terms) for i in range(lo, hi)]
            if hi < len(units):
                shown.append(UnitView(Markup("…"), "…", False, "gap"))
            views.append(
                PassageView(
                    part=para.part or s.part or "",
                    state="shown",
                    units=tuple(shown),
                    header=para.header,
                    **{**base, "note": note},
                )
            )
            note = None
    return views


def page_to_dict(page: PageEvidence, registry: SourceRegistry | None = None) -> dict:
    """JSON form. Each support carries its short `quotes`; the surrounding `passage` appears only
    when the document exists on this machine."""
    claims = []
    for i, v in enumerate(page.claims, 1):
        item: dict = {
            "n": i,
            "id": v.claim.id,
            "section": v.claim.section,
            "kind": v.claim.kind,
            "text": v.claim.text,
            "state": v.state,
        }
        if v.entry:
            item["how"] = v.entry.how
            item["note"] = v.entry.note
            shown = passages(v.entry, v.claim, registry)
            item["support"] = [
                s.model_dump(exclude_none=True)
                | {"where": _where(s.doc, s.at)}
                | (
                    {
                        "passage": [
                            {"text": u.text, "cited": u.cited}
                            for p in shown
                            if (p.doc, p.at) == (s.doc, s.at)
                            for u in p.units
                        ]
                    }
                    if registry and registry[s.doc].available
                    else {}
                )
                for s in v.entry.support
            ]
        claims.append(item)
    return {
        "kind": page.kind,
        "slug": page.slug,
        "title": page.title,
        "status": page.status,
        "total": page.total,
        "counts": page.counts(),
        "grounded": page.grounded,
        "open": page.open,
        "claims": claims,
    }
