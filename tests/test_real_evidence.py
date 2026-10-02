"""The repository's own evidence ledgers (not fixtures)."""

import pytest

from docx86 import evidence as ev
from docx86.config import PROJECT_ROOT, get_settings
from docx86.content import load_content
from docx86.sources import SourceRegistry


@pytest.fixture(scope="module")
def store():
    content = load_content(PROJECT_ROOT / "content")
    return ev.EvidenceStore(content, PROJECT_ROOT / "content" / "evidence")


def test_every_ledger_is_valid_and_matches_its_page(store):
    """No stale claims, bad entries or orphan files; reviewed pages are fully covered."""
    rep = ev.check(store, None, PROJECT_ROOT)
    assert not rep.problems, "\n".join(rep.problems)


def test_no_ledger_contains_source_text(store):
    """Ledgers hold pointers. A long free-text field would be a sign of pasted source prose."""
    for page in store.pages():
        for view in page.claims:
            e = view.entry
            if e is None:
                continue
            assert len(e.note or "") <= 400, f"{page.slug}: note on {e.id} is suspiciously long"
            for s in e.support:
                assert len(s.note or "") <= 300, f"{page.slug}: support note on {e.id} is long"
                assert all(len(u) == 10 for u in s.units)


def test_no_instruction_page_has_open_claims(store):
    """Every statement of every instruction page was read against the sources (or classified)."""
    open_pages = {p.slug: p.counts() for p in store.pages("instruction") if p.open}
    assert not open_pages, f"claims without evidence: {open_pages}"


def test_nothing_rests_on_an_unconfirmed_suggestion(store):
    """`suggest --write` output must be read and confirmed (or replaced) before it is committed."""
    pending = {p.slug: p.counts()["suggested"] for p in store.pages() if p.counts()["suggested"]}
    assert not pending, f"unconfirmed suggestions: {pending}"


def test_run_evidence_points_at_programs_in_the_repository(store):
    refs = {
        v.entry.ref for p in store.pages() for v in p.claims if v.entry and v.entry.how == "run"
    }
    assert refs and all((PROJECT_ROOT / r).exists() for r in refs)
    assert all(r.startswith("tests/asm/") for r in refs)


def test_pointers_resolve_in_the_local_documents(store):
    """Runs only where the reference documents were downloaded (see README, Development)."""
    registry = SourceRegistry(get_settings(), PROJECT_ROOT / ".cache")
    if not any(s.available for s in registry.all()):
        pytest.skip("no reference document downloaded")
    rep = ev.check(store, registry, PROJECT_ROOT)
    assert not rep.problems, "\n".join(rep.problems[:20])
