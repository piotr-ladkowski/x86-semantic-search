"""`docx86 evidence ...`: look at, record and check the evidence ledgers (see docs/EVIDENCE.md)."""

from __future__ import annotations

import argparse
import sys
import textwrap

from . import evidence as ev
from .config import PROJECT_ROOT, Settings
from .content import Content, ContentError, load_content
from .sources import SourceRegistry

BAR = 24


def _setup(settings: Settings) -> tuple[Content, ev.EvidenceStore, SourceRegistry]:
    try:
        content = load_content(settings.content_dir)
    except ContentError as err:
        print(err, file=sys.stderr)
        raise SystemExit(1) from None
    return (
        content,
        ev.EvidenceStore(content, settings.content_dir / "evidence"),
        SourceRegistry(settings, settings.cache_dir),
    )


def _page(store: ev.EvidenceStore, slug: str, kind: str | None) -> ev.PageEvidence:
    hits = [p for p in store.pages(kind) if p.slug == slug.lower()]
    if len(hits) != 1:
        which = f" ({kind})" if kind else ""
        sys.exit(
            f"No unique page '{slug}'{which}."
            + (" Use --kind instruction|article." if len(hits) > 1 else "")
        )
    return hits[0]


def _bar(page: ev.PageEvidence) -> str:
    c = page.counts()
    if not page.total:
        return ""
    filled = round(BAR * page.grounded / page.total)
    sug = round(BAR * c["suggested"] / page.total)
    return (
        "█" * filled + "▒" * min(sug, BAR - filled) + "·" * (BAR - filled - min(sug, BAR - filled))
    )


def _counts_line(counts: dict[str, int]) -> str:
    return ", ".join(f"{n} {s}" for s, n in counts.items() if n)


# -- status ---------------------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace, settings: Settings) -> int:
    _content, store, registry = _setup(settings)
    if args.slug:
        return _show(_page(store, args.slug, args.kind), registry, args, brief=True)
    print(f"{'page':<26}{'claims':>7}  {'coverage':<{BAR}}  breakdown")
    for page in store.pages():
        tag = "" if page.kind == "instruction" else " (article)"
        print(f"{page.slug + tag:<26}{page.total:>7}  {_bar(page)}  {_counts_line(page.counts())}")
    t = store.totals()
    total = sum(t.values())
    grounded = sum(t[s] for s in ev.GROUNDED)
    print(
        f"\n{total} claims: {grounded} rest on a source sentence "
        f"({100 * grounded // max(total, 1)}%), "
        f"{t['illustrative'] + t['editorial'] + t['external']} are examples, advice or outside "
        f"sources, {t['suggested']} have only an unconfirmed suggestion, {t['unverified']} are open"
    )
    print("█ rests on a source   ▒ suggested only   · other (examples, advice, open)")
    return 0


def _show(page: ev.PageEvidence, registry: SourceRegistry, args, brief: bool = False) -> int:
    print(f"# {page.slug} ({page.kind}, {page.status}): {_counts_line(page.counts())}")
    if not brief and not page.ledger_exists:
        print(f"(no ledger yet: {page.path})")
    for i, v in enumerate(page.claims, 1):
        if args.only and v.state not in args.only:
            continue
        e = v.entry
        head = f"{i:>3} {v.state:<12} {v.claim.id}  [{v.claim.section}] "
        print(head + textwrap.shorten(ev.plain_text(v.claim.text), 96, placeholder="…"))
        if brief or e is None:
            continue
        if e.note:
            print(f"      note: {e.note}")
        if e.ref:
            print(f"      run: {e.ref}")
        for p in ev.passages(e, v.claim, registry):
            print(f"      -> {p.doc_label}, {p.where}{', ' + p.part if p.part else ''} ({p.by})")
            if p.state != "shown":
                what = "text not available here" if p.state == "unavailable" else "NOT FOUND"
                print(f"         ({what})")
            for u in p.units:
                text = textwrap.shorten(u.text, 300, placeholder=" …")
                print(f"         {'►' if u.cited else ' '} {text}")
    for e in page.stale:
        print(f"  STALE {e.id} {e.gist!r}: the claim's wording changed or it was removed")
    return 0


def cmd_show(args: argparse.Namespace, settings: Settings) -> int:
    _content, store, registry = _setup(settings)
    return _show(_page(store, args.slug, args.kind), registry, args)


# -- find / cite / mark ---------------------------------------------------------------------------


def _locator(doc: str, at: str) -> int | str:
    return int(at) if doc in ("sdm", "sysv") else at


def cmd_find(args: argparse.Namespace, settings: Settings) -> int:
    _content, _store, registry = _setup(settings)
    source = registry[args.doc]
    if not source.available:
        print(f"{source.label} is not available here: {source.download}", file=sys.stderr)
        return 1
    if args.at is None and args.doc in ("msx64", "msstack", "wikibooks"):
        for title in source.section_titles():  # type: ignore[attr-defined]
            print(title)
        return 0
    if args.at is None:
        sys.exit("give a PDF page number (docx86 sdm find <text> lists the pages of an entry)")
    at = _locator(args.doc, args.at)
    shown = 0
    for loc in source.units(at):
        if args.grep and args.grep.lower() not in loc.unit.text.lower():
            continue
        shown += 1
        text = loc.unit.text if args.full else textwrap.shorten(loc.unit.text, 140, placeholder="…")
        print(f"{loc.unit.id}  {loc.unit.kind[:4]:<4} {loc.unit.part[:22]:<22} {text}")
    if not shown:
        print("no matching sentence", file=sys.stderr)
        return 1
    return 0


def cmd_cite(args: argparse.Namespace, settings: Settings) -> int:
    _content, store, registry = _setup(settings)
    page = _page(store, args.slug, args.kind)
    view = page.selector(args.claim)
    source = registry[args.doc]
    if not source.available:
        sys.exit(f"{source.label} is not available here, so the pointer cannot be checked.")
    at = _locator(args.doc, args.at)
    wanted = [u for u in (args.unit or "").split(",") if u]
    located = [loc for loc in source.units(at)]
    if args.grep:
        wanted += [loc.unit.id for loc in located if args.grep.lower() in loc.unit.text.lower()]
    known = {loc.unit.id: loc for loc in located}
    bad = [u for u in wanted if u not in known]
    if not wanted or bad:
        sys.exit(f"no such sentence on {args.doc} {at}: {bad or args.grep or '(nothing selected)'}")
    wanted = list(dict.fromkeys(wanted))
    part = args.part or known[wanted[0]].unit.part or None
    entry = ev.Entry(
        id=view.claim.id,
        support=[
            ev.Support(doc=args.doc, at=at, units=wanted, part=part, by=args.by, note=args.note)
        ],
    )
    ledger = ev.record(page, [entry])
    ev.save(page, ledger)
    print(f"{page.slug} claim {view.claim.id}: cited {len(wanted)} sentence(s) of {args.doc} {at}")
    for u in wanted:
        print("  ► " + textwrap.shorten(known[u].unit.text, 200, placeholder="…"))
    return 0


def cmd_mark(args: argparse.Namespace, settings: Settings) -> int:
    _content, store, _registry = _setup(settings)
    page = _page(store, args.slug, args.kind)
    if args.how == "run" and not args.ref:
        sys.exit("--as run needs --ref tests/asm/<program>")
    if args.how in ("derived", "external") and not args.note:
        sys.exit(f"--as {args.how} needs --note (how it follows / which outside source)")
    entries = [
        ev.Entry(
            id=page.selector(ref).claim.id,
            how=args.how,
            note=args.note,
            ref=args.ref,
            by=args.by,
        )
        for ref in args.claims
    ]
    ev.save(page, ev.record(page, entries))
    print(f"{page.slug}: marked {len(entries)} claim(s) as {args.how}")
    return 0


def cmd_retarget(args: argparse.Namespace, settings: Settings) -> int:
    """Move the evidence of a reworded claim (a stale id) onto the claim that replaced it."""
    _content, store, _registry = _setup(settings)
    page = _page(store, args.slug, args.kind)
    old = [e for e in page.stale if e.id.startswith(args.old)]
    if len(old) != 1:
        sys.exit(
            f"{args.old!r} matches {len(old)} stale entries of {page.slug} (see `evidence check`)"
        )
    target = page.selector(args.claim)
    moved = old[0].model_copy(update={"id": target.claim.id, "gist": ev.gist_of(target.claim.text)})
    kept = [v.entry for v in page.claims if v.entry]
    others = [e for e in page.stale if e is not old[0]]
    order = {v.claim.id: i for i, v in enumerate(page.claims)}
    entries = sorted([*kept, moved], key=lambda e: order[e.id]) + others
    ev.save(page, ev.Ledger(claims=entries))
    print(f"{page.slug}: evidence of {old[0].id} now belongs to claim {target.claim.id}")
    print("  Re-read the cited sentences against the new wording; `retarget` does not.")
    return 0


def cmd_prune(args: argparse.Namespace, settings: Settings) -> int:
    """Drop the evidence of claims that no longer exist (not carried over to a new wording)."""
    _content, store, _registry = _setup(settings)
    pages = [_page(store, args.slug, args.kind)] if args.slug else store.pages()
    dropped = 0
    for page in pages:
        if not page.stale:
            continue
        kept = [v.entry for v in page.claims if v.entry]
        ev.save(page, ev.Ledger(claims=kept))
        dropped += len(page.stale)
        print(
            f"{page.slug}: dropped {len(page.stale)} stale "
            f"entr{'y' if len(page.stale) == 1 else 'ies'}"
        )
    if not dropped:
        print("nothing stale")
    return 0


# -- suggest --------------------------------------------------------------------------------------


def _default_scope(content: Content, page: ev.PageEvidence, settings: Settings) -> list[str]:
    """Instruction pages: the pages of their SDM entries. Articles must say."""
    if page.kind != "instruction":
        return []
    from . import sdm

    entries = {e.title: e for e in sdm.load_entries(settings.sdm_pdf, settings.cache_dir)}
    ins = content.instructions[page.slug]
    return [
        f"sdm:{entries[t].first_page}-{entries[t].last_page}"
        for t in ins.sdm_entries
        if t in entries
    ]


def cmd_suggest(args: argparse.Namespace, settings: Settings) -> int:
    from . import suggest as sg
    from .embedding import get_embedder

    content, store, registry = _setup(settings)
    embedder = get_embedder(settings)
    if not args.all and not args.slug:
        sys.exit("give a page slug, or --all --write for every instruction page")
    if args.all and not args.write:
        sys.exit("--all only makes sense with --write (it would print hundreds of lines)")
    pages = (
        [p for p in store.pages() if p.kind == "instruction"]
        if args.all
        else [_page(store, args.slug, args.kind)]
    )
    for page in pages:
        scope = list(args.scope or []) or _default_scope(content, page, settings)
        scope += list(args.also or [])
        if not scope:
            print(
                f"{page.slug}: give --scope doc:pages (articles have no default)", file=sys.stderr
            )
            continue
        pool = sg.build_pool(registry, scope)
        found = sg.suggest(page, pool, embedder, top=args.top)
        if args.write:
            entries = sg.entries_from(found, min_score=args.min)
            if entries:
                ev.save(page, ev.record(page, entries))
            exact = sum(1 for e in entries if e.support[0].by == "match")
            print(
                f"{page.slug}: {len(pool)} candidate sentences; recorded {exact} exact and "
                f"{len(entries) - exact} suggested links for {len(found)} open claims"
            )
            continue
        print(f"# {page.slug}: {len(pool)} candidate sentences from {', '.join(scope)}")
        for i, v in enumerate(page.claims, 1):
            cands = found.get(v.claim.id)
            if cands is None:
                continue
            print(
                f"{i:>3} {v.claim.id} "
                + textwrap.shorten(ev.plain_text(v.claim.text), 90, placeholder="…")
            )
            for c in cands:
                u = c.unit
                print(
                    f"      {c.score:.2f} {c.method:<7} {u.doc} {u.at} {u.loc.unit.id} "
                    + textwrap.shorten(u.text, 110, placeholder="…")
                )
    return 0


# -- check ----------------------------------------------------------------------------------------


def cmd_check(args: argparse.Namespace, settings: Settings) -> int:
    _content, store, registry = _setup(settings)
    rep = ev.check(store, None if args.no_sources else registry, PROJECT_ROOT)
    for line in rep.problems:
        print(line, file=sys.stderr)
    for line in rep.notices:
        print(f"note: {line}", file=sys.stderr)
    t = store.totals()
    total = sum(t.values())
    grounded = sum(t[s] for s in ev.GROUNDED)
    print(
        f"{'FAILED' if rep.problems else 'OK'}: {total} claims on {len(store.pages())} pages, "
        f"{grounded} grounded in sources, {t['suggested']} suggested only, "
        f"{t['unverified']} open; {rep.resolved} source pointers confirmed, "
        f"{rep.unchecked} not looked up here"
    )
    return 1 if rep.problems else 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("evidence", help="which source sentence supports which claim of a page")
    actions = p.add_subparsers(dest="action", required=True)

    def kind(a: argparse.ArgumentParser) -> None:
        a.add_argument("--kind", choices=["instruction", "article"], help="if a slug is in both")

    a = actions.add_parser("status", help="coverage of every page, or the claims of one")
    a.add_argument("slug", nargs="?")
    kind(a)
    a.add_argument("--only", nargs="*", choices=ev.STATES, help="list only these states")
    a.set_defaults(func=cmd_status)

    a = actions.add_parser("show", help="a page's claims with the passages they cite")
    a.add_argument("slug")
    kind(a)
    a.add_argument("--only", nargs="*", choices=ev.STATES, help="list only these states")
    a.set_defaults(func=cmd_show)

    a = actions.add_parser("find", help="list the citable sentences of a source page or section")
    a.add_argument("doc", choices=["sdm", "sysv", "msx64", "msstack", "wikibooks"])
    a.add_argument("at", nargs="?", help="PDF page number, or section title for web documents")
    a.add_argument("--grep", help="only sentences containing this text")
    a.add_argument("--full", action="store_true", help="do not shorten the sentences")
    a.set_defaults(func=cmd_find)

    a = actions.add_parser("cite", help="record that sentences of a source support a claim")
    a.add_argument("slug")
    a.add_argument("claim", help="claim number, id or id prefix (see `evidence show`)")
    a.add_argument("--doc", required=True, choices=["sdm", "sysv", "msx64", "msstack", "wikibooks"])
    a.add_argument("--at", required=True, help="PDF page (where the sentence starts) or section")
    a.add_argument("--unit", help="comma-separated sentence ids from `evidence find`")
    a.add_argument("--grep", help="cite every sentence on that page containing this text")
    a.add_argument("--part", help="display label, default: the document's heading")
    a.add_argument("--by", choices=["llm", "human"], default="llm", help="who read the passage")
    a.add_argument("--note", help="why this passage supports the claim, if not obvious")
    kind(a)
    a.set_defaults(func=cmd_cite)

    a = actions.add_parser("mark", help="classify claims that have no source passage")
    a.add_argument("slug")
    a.add_argument("claims", nargs="+", help="claim numbers or ids")
    a.add_argument(
        "--as",
        dest="how",
        required=True,
        choices=["derived", "run", "illustrative", "editorial", "external"],
    )
    a.add_argument("--note", help="derived: how it follows; external: the outside source")
    a.add_argument("--ref", help="run: the program in tests/asm/ that checks it")
    a.add_argument("--by", choices=["llm", "human"], default="llm")
    kind(a)
    a.set_defaults(func=cmd_mark)

    a = actions.add_parser(
        "retarget", help="carry a reworded claim's evidence over to its new text"
    )
    a.add_argument("slug")
    a.add_argument("old", help="the stale id (or prefix) reported by `evidence check`")
    a.add_argument("claim", help="the current claim that replaces it: number, id or prefix")
    kind(a)
    a.set_defaults(func=cmd_retarget)

    a = actions.add_parser("prune", help="drop evidence of claims that no longer exist")
    a.add_argument("slug", nargs="?", help="default: every page")
    kind(a)
    a.set_defaults(func=cmd_prune)

    a = actions.add_parser("suggest", help="rank candidate source sentences for open claims")
    a.add_argument("slug", nargs="?")
    a.add_argument("--all", action="store_true", help="every instruction page (needs --write)")
    a.add_argument("--scope", action="append", help="doc:pages to search, e.g. sdm:1893-1895")
    a.add_argument("--also", action="append", help="extra doc:pages added to the default scope")
    a.add_argument("--top", type=int, default=3)
    a.add_argument("--write", action="store_true", help="record strong candidates as suggestions")
    a.add_argument("--min", type=float, default=0.6, help="--write: minimum score (default 0.6)")
    kind(a)
    a.set_defaults(func=cmd_suggest)

    a = actions.add_parser("check", help="validate every ledger (stale claims, bad pointers)")
    a.add_argument("--no-sources", action="store_true", help="do not look pointers up")
    a.set_defaults(func=cmd_check)
