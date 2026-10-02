"""The evidence pages, their JSON, and the single link from the existing pages."""

import pytest
from fastapi.testclient import TestClient

from docx86 import evidence as ev
from docx86.config import Settings
from docx86.content import load_content
from docx86.main import create_app
from docx86.textunits import digest

SOURCE_HTML = """<html><body><h1>Population count</h1>
<p>The instruction counts the bits set to 1. It stores the count in a register.</p></body></html>"""
COUNTS = digest("The instruction counts the bits set to 1.")


def make_settings(tmp_path, content_dir, *, with_source=True):
    html = tmp_path / "w.html"
    html.write_text(SOURCE_HTML, encoding="utf-8")
    return Settings(
        content_dir=content_dir,
        index_dir=tmp_path / "index",
        embedder="hash",
        rebuild_stale_index=True,
        wikibooks_html=html if with_source else tmp_path / "missing.html",
        sdm_pdf=tmp_path / "none.pdf",
        sysv_abi_pdf=tmp_path / "none2.pdf",
        ms_calling_convention_html=tmp_path / "none3.html",
        ms_stack_usage_html=tmp_path / "none4.html",
        cache_dir=tmp_path / "cache",
    )


def write_ledger(content_dir, entries, slug="popcnt", kind="instruction"):
    store = ev.EvidenceStore(load_content(content_dir), content_dir / "evidence")
    page = store.get(kind, slug)
    ids = [v.claim.id for v in page.claims]
    ev.save(page, ev.record(page, [entry(ids, *spec) for spec in entries]))
    return ids


def entry(ids, index, kw):
    return ev.Entry(id=ids[index], **kw)


def wiki(by="llm", unit=COUNTS):
    return ev.Support(doc="wikibooks", at="Population count", units=[unit], by=by)


@pytest.fixture
def app_client(tmp_path, content_dir):
    def make(*, with_source=True):
        settings = make_settings(tmp_path, content_dir, with_source=with_source)
        return TestClient(create_app(settings))

    return make


def get(app_client, url, **kw):
    with app_client(**kw) as c:
        return c.get(url)


def test_a_page_without_a_ledger_lists_its_claims_as_unchecked(app_client):
    r = get(app_client, "/instructions/popcnt/evidence")
    assert r.status_code == 200
    for needle in (
        "Summary of POPCNT.",
        "Does a thing.",
        "Be careful.",
        "No source has been recorded",
    ):
        assert needle in r.text, needle
    assert "0</strong> of 6 statements rest on a sentence" in r.text
    assert "<script" not in r.text  # no JavaScript is needed


def test_a_cited_sentence_is_highlighted_in_its_paragraph(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]})])
    r = get(app_client, "/instructions/popcnt/evidence")
    assert "<mark" in r.text and "The instruction counts the bits set to 1." in r.text
    assert "It stores the count in a register." in r.text  # the neighbouring sentence, unmarked
    assert "Wikibooks" in r.text and "read and checked by an AI" in r.text
    assert "Traced to a source" in r.text and "1</strong> of 6 statements rest" in r.text


def test_the_state_filter_lists_only_those_claims(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]}), (1, {"how": "editorial", "note": "n"})])
    r = get(app_client, "/instructions/popcnt/evidence?state=editorial")
    assert "Does a thing." not in r.text and "Be careful." not in r.text
    assert "Summary of POPCNT." not in r.text  # that one is traced, not editorial
    ignored = get(app_client, "/instructions/popcnt/evidence?state=bogus")
    assert "Be careful." in ignored.text  # an unknown state is ignored, not an error


def test_an_unconfirmed_suggestion_is_labelled_as_such(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki(by="auto")]})])
    r = get(app_client, "/instructions/popcnt/evidence")
    assert (
        "automatic suggestion, not confirmed" in r.text
        and "Suggested match (unconfirmed)" in r.text
    )
    assert "border-dashed" in r.text


def test_without_the_document_only_the_pointer_is_shown(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]})])
    r = get(app_client, "/instructions/popcnt/evidence", with_source=False)
    assert r.status_code == 200
    assert "The passage is not shown on this server" in r.text
    assert "The instruction counts the bits" not in r.text  # never republished
    assert "section “Population count”" in r.text  # but the pointer is


def test_derived_claims_show_their_note(app_client, content_dir):
    write_ledger(
        content_dir, [(1, {"how": "derived", "note": "Because of the loop.", "support": [wiki()]})]
    )
    r = get(app_client, "/instructions/popcnt/evidence")
    assert "Because of the loop." in r.text and "Derived from sources" in r.text


def test_evidence_that_no_longer_matches_is_listed(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]})])
    path = content_dir / "instructions" / "popcnt.md"
    path.write_text(path.read_text().replace("Summary of POPCNT.", "A new summary."))
    r = get(app_client, "/instructions/popcnt/evidence")
    assert "Evidence that no longer matches" in r.text and "Summary of POPCNT." in r.text


def test_aliases_redirect_and_unknown_pages_are_404(app_client):
    with app_client() as c:
        r = c.get("/instructions/sal/evidence", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, "/instructions/shl/evidence")
        assert c.get("/instructions/nope/evidence").status_code == 404
        assert c.get("/articles/nope/evidence").status_code == 404


def test_articles_have_evidence_pages_too(app_client):
    r = get(app_client, "/articles/regs/evidence")
    assert r.status_code == 200 and "Registers hold values." in r.text


def test_the_overview_lists_every_page_and_explains_the_states(app_client):
    r = get(app_client, "/evidence")
    assert r.status_code == 200
    for needle in ("Title of POPCNT", "About registers", "/instructions/popcnt/evidence", "Traced"):
        assert needle in r.text, needle
    assert "copyrighted" in r.text and "never their text" in r.text


def test_the_existing_pages_get_one_small_link(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]})])
    with app_client() as c:
        page = c.get("/instructions/popcnt").text
        assert 'href="/instructions/popcnt/evidence"' in page and "1 of 6 statements traced" in page
        assert 'href="/articles/regs/evidence"' in c.get("/articles/regs").text
        assert 'href="/evidence"' in c.get("/about").text
        assert 'href="/evidence"' in c.get("/").text  # footer


def test_json_summary_and_page(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]})])
    with app_client() as c:
        summary = c.get("/api/evidence").json()
        assert summary["totals"]["traced"] == 1
        assert {p["slug"] for p in summary["pages"]} == {"popcnt", "lea", "shl", "regs"}
        data = c.get("/api/evidence/instructions/popcnt").json()
        assert (
            data["total"] == 6 and data["grounded"] == 1 and data["claims"][0]["state"] == "traced"
        )
        passage = data["claims"][0]["support"][0]["passage"]
        assert passage[0]["cited"] is True
        assert c.get("/api/evidence/articles/regs").status_code == 200
        assert c.get("/api/evidence/instructions/nope").status_code == 404
        assert c.get("/api/evidence/other/popcnt").status_code == 422


def test_json_leaves_out_source_text_when_the_document_is_absent(app_client, content_dir):
    write_ledger(content_dir, [(0, {"support": [wiki()]})])
    data = get(app_client, "/api/evidence/instructions/popcnt", with_source=False).json()
    support = data["claims"][0]["support"][0]
    assert "passage" not in support and support["where"] == "section “Population count”"
