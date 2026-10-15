"""`docx86` command line: content validation, index build, progress, SDM lookup."""

from __future__ import annotations

import argparse
import sys

from .config import PROJECT_ROOT, Settings, get_settings
from .content import ContentError, load_content


def _load(settings: Settings):
    try:
        return load_content(settings.content_dir)
    except ContentError as err:
        print(err, file=sys.stderr)
        raise SystemExit(1) from None


def cmd_validate(args: argparse.Namespace, settings: Settings) -> int:
    content = _load(settings)
    print(
        f"OK: {len(content.instructions)} instruction page(s), {len(content.articles)} article(s), "
        f"{len(content.roster.instructions)} in roster"
    )
    if args.sdm:
        from . import sdm

        titles = {e.title for e in sdm.load_entries(settings.sdm_pdf, PROJECT_ROOT / ".cache")}
        missing = [
            f"roster '{r.slug}': SDM entry not found: {t!r}"
            for r in content.roster.instructions
            for t in r.sdm
            if t not in titles
        ]
        if missing:
            print("\n".join(missing), file=sys.stderr)
            return 1
        print(f"OK: all roster SDM entries exist in {settings.sdm_pdf.name}")
    return 0


def cmd_build_index(_: argparse.Namespace, settings: Settings) -> int:
    from .embedding import get_embedder
    from .index import build_index, save_index

    content = _load(settings)
    embedder = get_embedder(settings)
    index = build_index(content, embedder)
    save_index(index, settings.index_dir)
    print(f"Indexed {len(index.units)} units with {embedder.id} -> {settings.index_dir}")
    return 0


def cmd_progress(args: argparse.Namespace, settings: Settings) -> int:
    from .progress import compute, sync

    content = _load(settings)
    try:
        stale = sync(content, PROJECT_ROOT, write=not args.check)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 1
    if args.check:
        if stale:
            print(
                "Out of date (run `make progress`): " + ", ".join(map(str, stale)), file=sys.stderr
            )
            return 1
        print("Progress files are up to date")
        return 0
    p = compute(content)
    print(f"{p.documented}/{p.total} documented; updated {len(stale)} file(s)")
    return 0


def cmd_sdm(args: argparse.Namespace, settings: Settings) -> int:
    from . import sdm

    entries = sdm.load_entries(settings.sdm_pdf, PROJECT_ROOT / ".cache")
    matches = sdm.find(entries, args.query)
    if not matches:
        print(f"No SDM entry matches {args.query!r}", file=sys.stderr)
        return 1
    if args.action == "find":
        for e in matches:
            print(f"{e.first_page}-{e.last_page}\t{e.title}")
        return 0
    if len(matches) > 1:
        # Several entries can share a mnemonic (MOV, MOV to/from control registers, ...). Take the
        # first exact-mnemonic match (the main entry comes first); don't guess for fuzzy matches.
        if not sdm.is_exact(matches[0], args.query):
            print("Ambiguous; use a more specific query or `sdm find`:", file=sys.stderr)
            for e in matches:
                print(f"  {e.first_page}-{e.last_page}\t{e.title}", file=sys.stderr)
            return 1
        others = "; ".join(f"{e.first_page}: {e.title}" for e in matches[1:])
        print(f"(also matches: {others})", file=sys.stderr)
    e = matches[0]
    last = min(e.last_page, e.first_page + args.max_pages - 1)
    print(f"# {e.title}  (PDF pages {e.first_page}-{e.last_page})")
    print(sdm.read_pages(settings.sdm_pdf, e.first_page, last))
    return 0


def cmd_eval(_: argparse.Namespace, settings: Settings) -> int:
    """Run content/eval.yaml against the index.

    Fails if an expected page ranks outside its `top` bar (default 3), or if a query from
    `negatives` still clears the relevance floor. Also prints what the floor rests on: the
    weakest expected page and the strongest negative, so the margin is visible on every run.
    """
    import yaml

    from .embedding import get_embedder
    from .index import ensure_fresh, load_index
    from .search import SearchEngine

    content = _load(settings)
    embedder = get_embedder(settings)
    index = load_index(settings.index_dir)
    ensure_fresh(index, content, embedder)
    engine = SearchEngine(content, index, embedder, floor=settings.search_floor)

    data = yaml.safe_load((settings.content_dir / "eval.yaml").read_text(encoding="utf-8"))
    queries, negatives = data["queries"], data.get("negatives", [])
    top1 = top3 = misses = 0
    expected_scores: list[float] = []
    below_floor: list[str] = []
    for item in queries:
        bar = int(item.get("top", 3))
        hits = engine.search(item["query"], kind=item.get("kind", "instruction"), limit=10)
        slugs = [h.slug for h in hits]
        rank = slugs.index(item["expect"]) + 1 if item["expect"] in slugs else None
        ok = rank is not None and rank <= bar
        misses += not ok
        top1 += rank == 1
        top3 += rank is not None and rank <= 3
        detail = ""
        if rank is not None:
            hit = hits[rank - 1]
            expected_scores.append(hit.score)
            if hit.weak:
                below_floor.append(f"{item['expect']} ({hit.score:.3f}) for {item['query']!r}")
            # How safely the expected page holds its place: its lead over the best other page.
            other = next((h.score for h in hits if h.slug != item["expect"]), None)
            lead = f"{hit.score - other:+.3f}" if other is not None else "n/a"
            detail = f"score={hit.score:.3f} lead={lead}"
        mark = "ok  " if ok else "MISS"
        print(
            f"{mark} rank={rank}/{bar} {detail:<24} expect={item['expect']:<10} "
            f"got={slugs[:3]}  {item['query']!r}"
        )

    leaks = 0
    negative_scores: list[float] = []
    for q in negatives:
        hits = engine.search(q, limit=3)
        top = hits[0] if hits else None
        rejected = top is None or top.weak
        leaks += not rejected
        if top is not None:
            negative_scores.append(top.score)
            where = f"top={top.score:.3f} ({top.kind} {top.slug})"
        else:
            where = "no results"
        print(f"{'ok  ' if rejected else 'LEAK'} {where:<40} {q!r}")

    n = len(queries)
    print(
        f"hit@1 {top1}/{n}   hit@3 {top3}/{n}   misses {misses}   "
        f"negatives rejected {len(negatives) - leaks}/{len(negatives)}   embedder={embedder.id}"
    )
    if expected_scores and negative_scores:
        print(
            f"floor {engine.floor:.2f}: weakest expected page {min(expected_scores):.3f}, "
            f"strongest negative {max(negative_scores):.3f}"
        )
    for line in below_floor:
        print(f"warning: expected page is marked weak: {line}")
    return 0 if misses == 0 and leaks == 0 else 1


def cmd_wiki(args: argparse.Namespace, settings: Settings) -> int:
    from . import wikibooks

    sections = wikibooks.load_sections(settings.wikibooks_html, PROJECT_ROOT / ".cache")
    if args.action == "grep":
        hits = wikibooks.grep(sections, args.query)
        for sec, snippet in hits[: args.limit]:
            print(f"h{sec.level}  {sec.title}\n      ...{snippet}...")
        if not hits:
            print(f"No section contains {args.query!r}", file=sys.stderr)
            return 1
        print(
            f"({len(hits)} section(s) match; showing {min(len(hits), args.limit)})", file=sys.stderr
        )
        return 0
    matches = wikibooks.find(sections, args.query)
    if not matches:
        print(f"No section title matches {args.query!r} (try `wiki grep`)", file=sys.stderr)
        return 1
    if args.action == "find":
        for sec in matches:
            print(f"h{sec.level}  {sec.title}  ({len(sec.text)} chars)")
        return 0
    exact = [m for m in matches if m.title.lower() == args.query.lower()]
    chosen = (exact or matches)[0]
    if len(matches) > 1 and not exact:
        print("(also matches: " + "; ".join(m.title for m in matches[1:6]) + ")", file=sys.stderr)
    print(f"# {chosen.title}  (h{chosen.level}, {len(chosen.text)} chars)\n")
    print(chosen.text[: args.max_chars])
    if len(chosen.text) > args.max_chars:
        print(f"\n[... truncated; use --max-chars {len(chosen.text)} for all]", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docx86", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate content/ (schema, cross-references, roster)")
    p.add_argument("--sdm", action="store_true", help="also check roster SDM titles in the PDF")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("build-index", help="embed content and write the search index")
    p.set_defaults(func=cmd_build_index)

    p = sub.add_parser("progress", help="regenerate README progress block + content/README.md")
    p.add_argument("--check", action="store_true", help="fail instead of writing if out of date")
    p.set_defaults(func=cmd_progress)

    p = sub.add_parser("eval", help="check search quality against content/eval.yaml")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("sdm", help="look up an instruction in the local Intel SDM PDF")
    p.add_argument("action", choices=["find", "show"])
    p.add_argument("query", help="mnemonic (ADD, POPCNT, SHL) or part of an entry title")
    p.add_argument("--max-pages", type=int, default=6, help="`show`: pages to print (default 6)")
    p.set_defaults(func=cmd_sdm)

    p = sub.add_parser("wiki", help="look up a section of the Wikibooks x86 Assembly print version")
    p.add_argument("action", choices=["find", "show", "grep"])
    p.add_argument(
        "query", help="`find`/`show`: words in a section title; `grep`: text in the body"
    )
    p.add_argument("--max-chars", type=int, default=6000, help="`show`: characters to print")
    p.add_argument("--limit", type=int, default=15, help="`grep`: matches to print")
    p.set_defaults(func=cmd_wiki)

    from . import evidence_cli

    evidence_cli.register(sub)

    args = parser.parse_args(argv)
    return args.func(args, get_settings())


if __name__ == "__main__":
    raise SystemExit(main())
