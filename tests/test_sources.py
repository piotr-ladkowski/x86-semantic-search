"""Reading reference documents into citable units, with small synthetic documents."""

import pytest

from docx86.config import Settings
from docx86.sources import SDM_HEADINGS, HtmlSource, PdfSource, SourceRegistry
from docx86.textunits import digest

pymupdf = pytest.importorskip("pymupdf")


def make_pdf(path, pages):
    """pages: list of [(y, text)]; the page is 612x792 points, text is laid out in a text box."""
    doc = pymupdf.open()
    for items in pages:
        page = doc.new_page()
        for y, text in items:
            page.insert_textbox(pymupdf.Rect(72, y, 540, y + 80), text, fontsize=10)
    doc.save(path)


@pytest.fixture
def sdm_like(tmp_path):
    path = tmp_path / "sdm.pdf"
    make_pdf(
        path,
        [
            [
                (30, "ADD—Add"),  # running title: only on the first page of an entry
                (120, "Description"),
                (150, "Adds the source to the destination. It sets the flags (e.g. carry) too."),
                (230, "Flags Affected"),
                (260, "The OF flag is cleared. The first sentence of a long paragraph that"),
                (750, "3-12 Vol. 2A"),
            ],
            [
                (120, "continues on the next page. Then it ends."),
                (180, "Operation"),
                (210, "DEST := DEST + SRC;"),
                (750, "3-13 Vol. 2A"),
            ],
        ],
    )
    return PdfSource(
        "sdm", "Test SDM", path, "wget x", None, use_tables=False, headings=SDM_HEADINGS
    )


def texts(source, page):
    return [(loc.unit.part, loc.unit.text) for loc in source.units(page)]


def test_pdf_sentences_carry_their_heading_and_drop_running_text(sdm_like):
    got = texts(sdm_like, 1)
    assert ("Description", "Adds the source to the destination.") in got
    assert ("Description", "It sets the flags (e.g. carry) too.") in got
    assert not any("Vol. 2A" in t or t == "Add" for _p, t in got)  # footer and title are noise


def test_units_are_fingerprinted_by_their_wording(sdm_like):
    for loc in sdm_like.units(1):
        assert loc.unit.id == digest(loc.unit.text)
        assert loc.unit.page == 1


def test_a_paragraph_that_continues_on_the_next_page_belongs_to_the_page_it_starts_on(sdm_like):
    page1 = [t for _p, t in texts(sdm_like, 1)]
    assert any(t.startswith("The first sentence of a long paragraph that continues") for t in page1)
    page2 = [t for _p, t in texts(sdm_like, 2)]
    assert not any("continues on the next page" in t for t in page2)


def test_operation_pseudocode_is_one_code_unit(sdm_like):
    (loc,) = [loc for loc in sdm_like.units(2) if loc.paragraph.part == "Operation"]
    assert loc.unit.kind == "code" and loc.unit.text == "DEST := DEST + SRC;"


def test_find_and_search(sdm_like):
    unit_id = digest("The OF flag is cleared.")
    assert sdm_like.find(1, unit_id) is not None
    assert sdm_like.find(1, "0000000000") is None
    assert [loc.unit.text for loc in sdm_like.search(1, "sets the flags")] == [
        "It sets the flags (e.g. carry) too."
    ]


def test_a_missing_document_is_unavailable_not_an_error(tmp_path):
    source = PdfSource("sdm", "Missing", tmp_path / "nope.pdf", "wget x")
    assert not source.available
    assert source.paragraphs(1) == [] and list(source.units(1)) == []


def test_extraction_is_cached_on_disk(tmp_path, sdm_like):
    cached = PdfSource(
        "sdm", "Test", sdm_like.path, "wget x", tmp_path / "cache", headings=SDM_HEADINGS
    )
    first = texts(cached, 1)
    assert list((tmp_path / "cache" / "units").glob("sdm-*.json"))
    again = PdfSource(
        "sdm", "Test", sdm_like.path, "wget x", tmp_path / "cache", headings=SDM_HEADINGS
    )
    again._build = None  # type: ignore[assignment]  # a cache hit must not re-extract
    assert texts(again, 1) == first


def test_an_unwritable_cache_does_not_break_extraction(tmp_path, sdm_like):
    blocker = tmp_path / "file"
    blocker.write_text("x")  # a file where the cache directory should be
    source = PdfSource("sdm", "T", sdm_like.path, "wget x", blocker / "sub", headings=SDM_HEADINGS)
    assert texts(source, 1)


HTML = """<html><body>
<h1>Calling convention</h1>
<p>The first four arguments go in registers. Others go on the stack.</p>
<h2>Parameter passing</h2>
<p>Integers use RCX, RDX, R8 and R9. The caller reserves shadow space.</p>
<p>Second paragraph here.</p>
</body></html>"""


@pytest.fixture
def html_source(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(HTML, encoding="utf-8")
    return HtmlSource("msx64", "Test page", path, "wget x")


def test_html_sections_are_listed_and_split_into_sentences(html_source):
    assert html_source.section_titles() == ["Calling convention", "Parameter passing"]
    got = [loc.unit.text for loc in html_source.units("Parameter passing")]
    assert got == [
        "Integers use RCX, RDX, R8 and R9.",
        "The caller reserves shadow space.",
        "Second paragraph here.",
    ]


def test_html_units_have_no_page_but_a_part(html_source):
    loc = html_source.find("Parameter passing", digest("The caller reserves shadow space."))
    assert loc is not None and loc.unit.page is None and loc.unit.part == "Parameter passing"
    assert loc.paragraph.index == 0 and len(loc.paragraph.units) == 2


def test_an_unknown_section_has_no_units(html_source):
    assert html_source.paragraphs("No such section") == []


def test_registry_knows_every_document(tmp_path):
    reg = SourceRegistry(Settings(wikibooks_html=tmp_path / "w.html"))
    assert {s.id for s in reg.all()} == {"sdm", "sysv", "msx64", "msstack", "wikibooks"}
    assert "sdm" in reg and "nope" not in reg
    assert reg["wikibooks"].download.startswith("wget ")
    assert not reg["wikibooks"].available
