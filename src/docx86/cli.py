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
    """Run content/eval.yaml against the index; fail if an expected page is outside the top 3."""
    import yaml

    from .embedding import get_embedder
    from .index import ensure_fresh, load_index
    from .search import SearchEngine

    content = _load(settings)
    embedder = get_embedder(settings)
    index = load_index(settings.index_dir)
    ensure_fresh(index, content, embedder)
    engine = SearchEngine(content, index, embedder)

    queries = yaml.safe_load((settings.content_dir / "eval.yaml").read_text(encoding="utf-8"))
    top1 = top3 = 0
    for item in queries["queries"]:
        hits = engine.search(item["query"], kind="instruction", limit=10)
        slugs = [h.slug for h in hits]
        rank = slugs.index(item["expect"]) + 1 if item["expect"] in slugs else None
        top1 += rank == 1
        top3 += rank is not None and rank <= 3
        mark = "ok  " if rank and rank <= 3 else "MISS"
        print(f"{mark} rank={rank}  expect={item['expect']:<8} got={slugs[:3]}  {item['query']!r}")
    n = len(queries["queries"])
    print(f"hit@1 {top1}/{n}   hit@3 {top3}/{n}   embedder={embedder.id}")
    return 0 if top3 == n else 1


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

    args = parser.parse_args(argv)
    return args.func(args, get_settings())


if __name__ == "__main__":
    raise SystemExit(main())
