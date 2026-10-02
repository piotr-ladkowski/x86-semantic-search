"""The evidence ledger: states, recording, stale detection, checking, and showing passages."""

import pytest
import yaml
from markupsafe import Markup

from docx86 import evidence as ev
from docx86.config import Settings
from docx86.content import load_content
from docx86.sources import SourceRegistry
from docx86.textunits import SPLITTER_VERSION, digest

SOURCE_HTML = """<html><body>
<h1>Population count</h1>
<p>The instruction counts the bits set to 1. It stores the count in a register.
Nothing here touches the &lt;i&gt;flags&lt;/i&gt;.</p>
<p>Unrelated second paragraph.</p>
</body></html>"""
COUNTS = digest("The instruction counts the bits set to 1.")
STORES = digest("It stores the count in a register.")


@pytest.fixture
def root(tmp_path):
    return tmp_path


@pytest.fixture
def store(content_dir):
    return ev.EvidenceStore(load_content(content_dir), content_dir / "evidence")


@pytest.fixture
def registry(tmp_path):
    html = tmp_path / "w.html"
    html.write_text(SOURCE_HTML, encoding="utf-8")
    return SourceRegistry(
        Settings(wikibooks_html=html, sdm_pdf=tmp_path / "none.pdf"), tmp_path / "cache"
    )


def popcnt(store):
    page = store.get("instruction", "popcnt")
    assert page is not None
    return page


def src(unit=COUNTS, by="llm", doc="wikibooks", at="Population count", **kw):
    return ev.Support(doc=doc, at=at, units=[unit], by=by, **kw)


def reload(store, content_dir):
    return ev.EvidenceStore(load_content(content_dir), content_dir / "evidence")


# ---- states and totals -----------------------------------------------------------------------


def test_a_page_without_a_ledger_has_only_unverified_claims(store):
    page = popcnt(store)
    assert not page.ledger_exists and page.total == 6
    assert page.counts()["unverified"] == 6 and page.grounded == 0 and page.open == 6


def test_state_depends_on_who_made_the_link(store):
    page = popcnt(store)
    ids = [v.claim.id for v in page.claims]
    ledger = ev.record(
        page,
        [
            ev.Entry(id=ids[0], support=[src(by="llm")]),
            ev.Entry(id=ids[1], support=[src(by="match")]),
            ev.Entry(id=ids[2], support=[src(by="auto")]),
            ev.Entry(id=ids[3], how="derived", note="because", support=[src()]),
            ev.Entry(id=ids[4], how="editorial", note="advice"),
            ev.Entry(id=ids[5], how="illustrative"),
        ],
    )
    assert [ev.state_of(e) for e in ledger.claims] == [
        "traced", "traced", "suggested", "derived", "editorial", "illustrative",
    ]  # fmt: skip
    assert ev.state_of(None) == "unverified"


def test_counts_and_percentages_after_reloading_the_ledger(content_dir, store):
    page = popcnt(store)
    ids = [v.claim.id for v in page.claims]
    ev.save(
        page,
        ev.record(
            page,
            [
                ev.Entry(id=ids[0], support=[src()]),
                ev.Entry(id=ids[1], support=[src(by="auto")]),
                ev.Entry(id=ids[2], how="editorial"),
            ],
        ),
    )
    again = popcnt(reload(store, content_dir))
    assert again.ledger_exists
    assert again.counts() == {
        "traced": 1, "derived": 0, "run": 0, "illustrative": 0, "editorial": 1,
        "external": 0, "suggested": 1, "unverified": 3,
    }  # fmt: skip
    assert (again.grounded, again.open, again.percent_grounded) == (1, 4, 17)


def test_totals_add_up_over_all_pages(store):
    assert sum(store.totals().values()) == sum(p.total for p in store.pages())
    assert {p.kind for p in store.pages()} == {"instruction", "article"}
    assert [p.slug for p in store.pages("article")] == ["regs"]


def test_urls(store):
    page = popcnt(store)
    assert page.url == "/instructions/popcnt/evidence" and page.page_url == "/instructions/popcnt"
    assert store.get("article", "regs").url == "/articles/regs/evidence"


# ---- recording -------------------------------------------------------------------------------


def test_ledger_file_is_readable_yaml_in_page_order(content_dir, store):
    page = popcnt(store)
    last, first = page.claims[-1].claim.id, page.claims[0].claim.id
    ev.save(
        page,
        ev.record(page, [ev.Entry(id=last, how="editorial"), ev.Entry(id=first, support=[src()])]),
    )
    text = page.path.read_text(encoding="utf-8")
    assert text.startswith("# Evidence ledger") and "Pointers only" in text
    data = yaml.safe_load(text)
    assert data["splitter"] == SPLITTER_VERSION
    assert [e["id"] for e in data["claims"]] == [first, last]  # page order, not insertion order
    assert data["claims"][0]["gist"] == "Summary of POPCNT."
    assert data["claims"][0]["support"] == [
        {"doc": "wikibooks", "at": "Population count", "units": [COUNTS]}
    ]


def test_an_auto_suggestion_replaces_older_guesses_but_never_confirmed_links(store):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    first = ev.record(page, [ev.Entry(id=cid, support=[src(STORES, by="auto")])])
    ev.save(page, first)
    page.claims[0].entry = first.claims[0]
    second = ev.record(page, [ev.Entry(id=cid, support=[src(COUNTS, by="auto")])])
    assert [s.units for s in second.claims[0].support] == [[COUNTS]]  # replaced, not added
    page.claims[0].entry = ev.Entry(id=cid, support=[src(STORES, by="llm")])
    third = ev.record(page, [ev.Entry(id=cid, support=[src(COUNTS, by="auto")])])
    assert [(s.units, s.by) for s in third.claims[0].support] == [
        ([STORES], "llm"),
        ([COUNTS], "auto"),
    ]


def test_a_confirmed_link_does_not_promote_the_guesses_beside_it(store):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    page.claims[0].entry = ev.Entry(id=cid, support=[src(STORES, by="auto")])
    merged = ev.record(page, [ev.Entry(id=cid, support=[src(COUNTS, by="llm")])])
    (only,) = merged.claims[0].support
    assert (only.units, only.by) == ([COUNTS], "llm")  # the unconfirmed guess is gone


def test_confirmed_links_to_the_same_place_are_merged(store):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    page.claims[0].entry = ev.Entry(id=cid, support=[src(COUNTS, by="match")])
    merged = ev.record(page, [ev.Entry(id=cid, support=[src(STORES, by="human")])])
    (only,) = merged.claims[0].support
    assert only.units == [COUNTS, STORES] and only.by == "human"


def test_classifying_a_claim_keeps_confirmed_links_and_drops_guesses(store):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    page.claims[0].entry = ev.Entry(
        id=cid, support=[src(COUNTS, by="llm"), src(STORES, by="auto", at="Other")]
    )
    merged = ev.record(page, [ev.Entry(id=cid, how="derived", note="because")])
    assert merged.claims[0].how == "derived"
    assert [s.units for s in merged.claims[0].support] == [[COUNTS]]


def test_selector_by_number_id_prefix_and_ambiguity(store):
    page = popcnt(store)
    assert page.selector("1") is page.claims[0]
    assert page.selector(page.claims[2].claim.id[:6]) is page.claims[2]
    with pytest.raises(KeyError):
        page.selector("zzzz")
    with pytest.raises(KeyError):
        page.selector("")  # matches every claim


def test_yaml_scalars_that_look_like_numbers_survive_a_round_trip(store, content_dir):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    section = "2024"
    ev.save(page, ev.record(page, [ev.Entry(id=cid, support=[src(at=section)])]))
    support = popcnt(reload(store, content_dir)).claims[0].entry.support[0]
    assert support.at == "2024" and isinstance(support.at, str)


# ---- checking --------------------------------------------------------------------------------


def run_check(store, registry=None, root=None):
    return ev.check(store, registry, root or store.dir.parent)


def test_a_clean_ledger_passes(store, content_dir, registry):
    page = popcnt(store)
    ev.save(page, ev.record(page, [ev.Entry(id=page.claims[0].claim.id, support=[src()])]))
    rep = run_check(reload(store, content_dir), registry)
    assert rep.problems == [] and rep.resolved == 1


def test_editing_a_claim_orphans_its_evidence_and_says_which_one(store, content_dir):
    page = popcnt(store)
    ev.save(page, ev.record(page, [ev.Entry(id=page.claims[0].claim.id, support=[src()])]))
    path = content_dir / "instructions" / "popcnt.md"
    path.write_text(path.read_text().replace("Summary of POPCNT.", "Summary of POPCNT, reworded."))
    fresh = reload(store, content_dir)
    assert popcnt(fresh).claims[0].state == "unverified"  # the old evidence no longer counts
    (problem,) = run_check(fresh).problems
    assert "no longer exists" in problem and "Summary of POPCNT." in problem
    assert "closest current claim" in problem and "reworded" in problem


def test_entry_problems(store, content_dir, root):
    page = popcnt(store)
    a, b, c = (page.claims[i].claim.id for i in (0, 1, 2))
    ev.save(
        page,
        ev.Ledger(
            claims=[
                ev.Entry(id=a, how="source"),
                ev.Entry(id=b, how="derived"),
                ev.Entry(id=c, how="run", ref="tests/asm/missing.asm"),
                ev.Entry(id=page.claims[3].claim.id, how="run"),
                ev.Entry(id=page.claims[4].claim.id, how="external"),
            ]
        ),
    )
    problems = "\n".join(run_check(reload(store, content_dir), root=root).problems)
    assert "how=source needs at least one `support`" in problems
    assert "how=derived needs a `note`" in problems
    assert "ref 'tests/asm/missing.asm' does not exist" in problems
    assert "how=run needs `ref`" in problems
    assert "how=external needs a `note`" in problems


def test_run_refs_are_looked_up_relative_to_the_repository(store, content_dir, root):
    (root / "tests").mkdir()
    (root / "tests" / "prog.asm").write_text("nop")
    page = popcnt(store)
    ev.save(
        page,
        ev.record(page, [ev.Entry(id=page.claims[0].claim.id, how="run", ref="tests/prog.asm")]),
    )
    assert run_check(reload(store, content_dir), root=root).problems == []


def test_a_reviewed_page_must_have_nothing_open(store, content_dir):
    path = content_dir / "instructions" / "popcnt.md"
    path.write_text(path.read_text().replace("status: draft", "status: reviewed"))
    fresh = reload(store, content_dir)
    (problem,) = [p for p in run_check(fresh).problems if "reviewed" in p]
    assert "6 claim(s) are unchecked" in problem
    page = popcnt(fresh)
    ev.save(page, ev.record(page, [ev.Entry(id=v.claim.id, how="editorial") for v in page.claims]))
    assert not [p for p in run_check(reload(store, content_dir)).problems if "reviewed" in p]


def test_suggestions_alone_do_not_satisfy_a_reviewed_page(store, content_dir):
    path = content_dir / "instructions" / "popcnt.md"
    path.write_text(path.read_text().replace("status: draft", "status: reviewed"))
    fresh = reload(store, content_dir)
    page = popcnt(fresh)
    ev.save(
        page,
        ev.record(page, [ev.Entry(id=v.claim.id, support=[src(by="auto")]) for v in page.claims]),
    )
    (problem,) = [p for p in run_check(reload(store, content_dir)).problems if "reviewed" in p]
    assert "only have unconfirmed suggestions" in problem


def test_ledger_for_a_page_that_does_not_exist(store, content_dir):
    orphan = content_dir / "evidence" / "instructions" / "ghost.yaml"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("claims: []\n")
    assert any(
        "no page with this slug" in p for p in run_check(reload(store, content_dir)).problems
    )


def test_unreadable_ledgers_are_reported_not_fatal(store, content_dir):
    page = popcnt(store)
    page.path.parent.mkdir(parents=True)
    page.path.write_text("claims: [{id: x, bogus: 1}]\n")
    fresh = reload(store, content_dir)  # must not raise
    assert popcnt(fresh).load_problems
    assert any("popcnt.yaml" in p for p in run_check(fresh).problems)
    page.path.write_text("claims: [unclosed\n")
    assert popcnt(reload(store, content_dir)).load_problems


def test_splitter_version_mismatch_is_a_problem(store, content_dir):
    page = popcnt(store)
    ev.save(page, ev.record(page, [ev.Entry(id=page.claims[0].claim.id, how="editorial")]))
    page.path.write_text(
        page.path.read_text().replace(f"splitter: {SPLITTER_VERSION}", "splitter: 0")
    )
    assert any("sentence splitter" in p for p in run_check(reload(store, content_dir)).problems)


def test_duplicate_entries_are_a_problem(store, content_dir):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    ev.save(
        page,
        ev.Ledger(claims=[ev.Entry(id=cid, how="editorial"), ev.Entry(id=cid, how="editorial")]),
    )
    assert any("listed more than once" in p for p in run_check(reload(store, content_dir)).problems)


# ---- looking the pointers up -----------------------------------------------------------------


def test_a_pointer_to_a_missing_sentence_is_a_problem(store, content_dir, registry):
    page = popcnt(store)
    ev.save(
        page, ev.record(page, [ev.Entry(id=page.claims[0].claim.id, support=[src("0000000000")])])
    )
    (problem,) = run_check(reload(store, content_dir), registry).problems
    assert "has no sentence 0000000000" in problem


def test_pointers_into_a_missing_document_are_not_checked_but_reported(
    store, content_dir, registry
):
    page = popcnt(store)
    sup = ev.Support(doc="sdm", at=1694, units=[COUNTS])
    ev.save(page, ev.record(page, [ev.Entry(id=page.claims[0].claim.id, support=[sup])]))
    rep = run_check(reload(store, content_dir), registry)
    assert rep.problems == [] and rep.unchecked == 1 and rep.resolved == 0
    assert any("not available here" in n and "wget" in n for n in rep.notices)
    assert run_check(reload(store, content_dir), None).notices == []  # --no-sources


def test_page_numbers_for_pdfs_and_titles_for_web_documents(store, content_dir, registry):
    page = popcnt(store)
    bad = [
        ev.Support(doc="sdm", at="1694", units=[COUNTS]),
        ev.Support(doc="wikibooks", at=12, units=[COUNTS]),
    ]
    ev.save(page, ev.record(page, [ev.Entry(id=page.claims[0].claim.id, support=bad)]))
    problems = run_check(reload(store, content_dir), registry).problems
    assert any("must be a PDF page number" in p for p in problems)
    assert any("must be a section title" in p for p in problems)


# ---- showing passages ------------------------------------------------------------------------


def test_the_cited_sentence_is_marked_with_its_neighbours_around_it(store, registry):
    claim = ev.Claim("x", "The count of bits set to 1.", "S", "prose")
    (p,) = ev.passages(ev.Entry(id="x", support=[src()]), claim, registry)
    assert (
        p.state == "shown"
        and p.doc_label.startswith("Wikibooks")
        and p.where == "section “Population count”"
    )
    assert [(u.text, u.cited) for u in p.units] == [
        ("The instruction counts the bits set to 1.", True),
        ("It stores the count in a register.", False),
        ("Nothing here touches the <i>flags</i>.", False),
    ]
    assert "<b>bits</b>" in p.units[0].html and "<b>count" in str(p.units[0].html)  # shared words


def test_words_shared_with_the_claim_are_emphasised_only_in_cited_sentences(registry):
    claim = ev.Claim("x", "It stores a register.", "S", "prose")
    (p,) = ev.passages(ev.Entry(id="x", support=[src(STORES)]), claim, registry)
    cited, other = p.units[1], p.units[0]
    assert "<b>stores</b>" in str(cited.html) and "<b>register</b>" in str(cited.html)
    assert "<b>" not in str(other.html)


def test_source_text_is_escaped(registry):
    claim = ev.Claim("x", "flags", "S", "prose")
    unit = digest("Nothing here touches the <i>flags</i>.")
    (p,) = ev.passages(ev.Entry(id="x", support=[src(unit)]), claim, registry)
    shown = "".join(str(u.html) for u in p.units)
    assert "<i>" not in shown and "&lt;i&gt;" in shown


def test_without_the_document_only_the_pointer_is_shown():
    claim = ev.Claim("x", "t", "S", "prose")
    (p,) = ev.passages(ev.Entry(id="x", support=[src()]), claim, None)
    assert (p.state, p.units, p.at) == ("unavailable", (), "Population count")


def test_a_pointer_that_no_longer_resolves_says_so(registry):
    claim = ev.Claim("x", "t", "S", "prose")
    (p,) = ev.passages(ev.Entry(id="x", support=[src("0000000000")]), claim, registry)
    assert p.state == "missing"


def test_long_paragraphs_are_cut_to_a_window_around_the_cited_sentences(tmp_path):
    sentences = [f"Sentence number {i} is here." for i in range(30)]
    html = tmp_path / "w.html"
    html.write_text(f"<h1>Long</h1><p>{' '.join(sentences)}</p>", encoding="utf-8")
    reg = SourceRegistry(Settings(wikibooks_html=html), tmp_path / "c")
    claim = ev.Claim("x", "Sentence 15", "S", "prose")
    unit = digest(sentences[15])
    (p,) = ev.passages(ev.Entry(id="x", support=[src(unit, at="Long")]), claim, reg)
    kinds = [u.kind for u in p.units]
    assert kinds[0] == "gap" and kinds[-1] == "gap" and len(p.units) == 2 + 7
    assert [u.cited for u in p.units].count(True) == 1


def test_key_terms_ignore_function_words_and_markdown():
    assert ev.key_terms("The `popcnt` instruction counts **bits**.") == {
        "popcnt",
        "instruction",
        "count",
        "bit",
    }
    assert isinstance(ev.emphasise("a <b> c", set()), Markup)
    assert str(ev.emphasise("a <b> c", set())) == "a &lt;b&gt; c"


def test_gist_keeps_identifiers_and_cuts_long_text():
    assert ev.gist_of("Use `__builtin_popcount` here.") == "Use __builtin_popcount here."
    assert len(ev.gist_of("word " * 50)) <= 64 and ev.gist_of("word " * 50).endswith("…")


def test_json_form_hides_source_text_unless_the_document_is_present(store, registry):
    page = popcnt(store)
    cid = page.claims[0].claim.id
    page.claims[0].entry = ev.Entry(id=cid, support=[src()])
    plain = ev.page_to_dict(page, None)
    assert (
        plain["claims"][0]["state"] == "traced"
        and "passage" not in plain["claims"][0]["support"][0]
    )
    assert plain["grounded"] == 1 and plain["total"] == 6
    local = ev.page_to_dict(page, registry)
    passage = local["claims"][0]["support"][0]["passage"]
    assert passage[0] == {"text": "The instruction counts the bits set to 1.", "cited": True}


def test_without_a_checkout_run_refs_are_not_looked_up(store, content_dir, root):
    """The image build has content/ but no tests/: `root=None` must not turn that into problems."""
    page = popcnt(store)
    ev.save(
        page,
        ev.record(page, [ev.Entry(id=page.claims[0].claim.id, how="run", ref="tests/asm/x.asm")]),
    )
    fresh = reload(store, content_dir)
    assert any("does not exist" in p for p in run_check(fresh, root=root).problems)
    assert ev.check(fresh, None, None).problems == []  # helper would default a None root
    (run,) = [v for v in popcnt(fresh).claims if v.state == "run"]
    assert run.entry.ref == "tests/asm/x.asm"  # still has to name a file
    page.path.write_text(page.path.read_text().replace("ref: tests/asm/x.asm\n", ""))
    assert any(
        "needs `ref`" in p for p in run_check(reload(store, content_dir), root=None).problems
    )
