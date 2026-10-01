"""Checks on the repository's real content/ directory (not fixtures)."""

from pathlib import Path

import pytest

from docx86.config import PROJECT_ROOT, get_settings
from docx86.content import load_content
from docx86.progress import sync


@pytest.fixture(scope="module")
def real():
    return load_content(PROJECT_ROOT / "content")


def test_real_content_is_valid(real):
    assert real.instructions and real.roster.instructions


def test_generated_progress_files_are_current(real):
    stale = sync(real, PROJECT_ROOT, write=False)
    assert not stale, f"run `make progress`: {stale}"


def test_excluded_and_deferred_have_no_pages(real):
    blocked = {
        m.lower() for g in (*real.roster.excluded, *real.roster.deferred) for m in g.mnemonics
    }
    assert not blocked & {i.mnemonic.lower() for i in real.instructions.values()}


def test_eval_queries_point_at_roster_slugs(real):
    import yaml

    data = yaml.safe_load((PROJECT_ROOT / "content" / "eval.yaml").read_text())
    planned = {e.slug for e in real.roster.instructions}
    for q in data["queries"]:
        if q.get("kind", "instruction") == "article":
            assert q["expect"] in real.articles, q
        else:
            assert q["expect"] in planned, q


@pytest.mark.skipif(not get_settings().sdm_pdf.exists(), reason="SDM PDF not downloaded")
def test_roster_sdm_titles_exist_in_pdf(real):
    from docx86 import sdm

    s = get_settings()
    titles = {e.title for e in sdm.load_entries(s.sdm_pdf, Path(PROJECT_ROOT) / ".cache")}
    missing = [t for r in real.roster.instructions for t in r.sdm if t not in titles]
    assert not missing


def test_internal_links_in_content_resolve(real):
    """A link to /instructions/x or /articles/x must point at a page that exists.

    Planned-but-unwritten instructions belong in `related:` (the UI skips those), not in links.
    """
    import re

    broken = []
    for owner, items in (("instruction", real.instructions), ("article", real.articles)):
        for slug, item in items.items():
            for m in re.finditer(r"\]\(/(instructions|articles)/([a-z0-9-]+)\)", item.body_md):
                kind, target = m.groups()
                pool = real.instructions if kind == "instructions" else real.articles
                if target not in pool:
                    broken.append(f"{owner} {slug}: /{kind}/{target}")
    assert not broken, "broken internal links:\n" + "\n".join(broken)
