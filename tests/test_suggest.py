"""Finding candidate source sentences: exact opcode matches and similarity ranking."""

import pytest

from docx86 import suggest as sg
from docx86.claims import Claim
from docx86.config import Settings
from docx86.embedding import HashEmbedder
from docx86.sources import Located, Paragraph, SourceRegistry, Unit
from docx86.textunits import digest


def row(text, page=10):
    unit = Unit(digest(text), text, "row", page, "Opcode table", 0)
    return sg.PoolUnit("sdm", page, Located(Paragraph(0, "Opcode table", page, [unit]), unit))


def sentence(text, doc="sdm", at=10):
    unit = Unit(digest(text), text, "sentence", at if doc == "sdm" else None, "Description", 0)
    return sg.PoolUnit(doc, at, Located(Paragraph(0, "Description", unit.page, [unit]), unit))


def form(syntax, opcode):
    text = f"`{syntax}` is encoded as `{opcode}`."
    return Claim(digest(text), text, "Forms", "fact")


ROWS = [
    row("REX.W + 01 /r | ADD r/m64, r64 | MR | Valid | N.E. | Add r64 to r/m64."),
    row("01 /r | ADD r/m32, r32 | MR | Valid | Valid | Add r32 to r/m32."),
    row("NP 90 | NOP | ZO | Valid | Valid | One byte no-operation instruction."),
    row("A4 | MOVS m8, m8 | ZO | Valid | Valid | Move byte."),
]


def test_a_form_matches_the_table_row_with_the_same_opcode_and_syntax():
    hit = sg.exact_form_match(form("ADD r/m64, r64", "REX.W + 01 /r"), ROWS)
    assert hit and hit.method == "match" and hit.score == 1.0 and "r/m64, r64" in hit.unit.text


def test_the_same_syntax_with_a_different_opcode_does_not_match():
    assert sg.exact_form_match(form("ADD r/m64, r64", "REX.W + 03 /r"), ROWS) is None
    assert sg.exact_form_match(form("ADD r/m32, r32", "REX.W + 01 /r"), ROWS) is None


def test_the_sdm_np_prefix_and_alternative_spellings_are_understood():
    assert sg.exact_form_match(form("NOP", "90"), ROWS)
    hit = sg.exact_form_match(form("MOVSB  (MOVS m8, m8)", "A4"), ROWS)
    assert hit and "MOVS m8, m8" in hit.unit.text


def test_only_form_claims_are_matched_mechanically():
    plain = Claim("x", "ADD adds numbers.", "S", "prose")
    assert sg.exact_form_match(plain, ROWS) is None


def test_similar_sentences_rank_first():
    pool = [
        sentence("The instruction counts the bits set to 1 in the source."),
        sentence("Moves a byte from one memory location to another."),
        sentence("Raises an exception when the segment limit is exceeded."),
    ]
    claim = Claim("c", "Counts the bits set to 1 in the source.", "Summary", "prose")
    best = sg.rank([claim], pool, HashEmbedder(), top=2)["c"]
    assert best[0].unit is pool[0] and best[0].method == "similar"
    assert best[0].score > best[1].score


def test_code_claims_get_no_suggestions():
    assert (
        sg.rank([Claim("c", "nop", "Example", "code")], [sentence("A sentence.")], HashEmbedder())
        == {}
    )


def test_suggest_prefers_exact_matches_and_skips_confirmed_claims(content_dir):
    from docx86.content import load_content
    from docx86.evidence import Entry, EvidenceStore, record, save

    store = EvidenceStore(load_content(content_dir), content_dir / "evidence")
    page = store.get("instruction", "popcnt")
    confirmed = page.claims[2].claim.id
    save(page, record(page, [Entry(id=confirmed, how="editorial")]))
    page = EvidenceStore(load_content(content_dir), content_dir / "evidence").get(
        "instruction", "popcnt"
    )
    pool = [
        row("REX.W + 00 /r | POPCNT r64, r/m64 | RM | Valid | N.E. | x"),
        sentence("Does a thing."),
    ]
    found = sg.suggest(page, pool, HashEmbedder())
    form_id = next(
        v.claim.id for v in page.claims if v.claim.kind == "fact" and "encoded" in v.claim.text
    )
    assert found[form_id][0].method == "match"
    assert confirmed not in found


def test_entries_keep_strong_candidates_and_label_who_made_them():
    pool = sentence("A sentence.")
    found = {
        "strong": [sg.Candidate(0.9, "similar", pool)],
        "weak": [sg.Candidate(0.2, "similar", pool)],
        "exact": [sg.Candidate(0.1, "match", pool)],
    }
    entries = {e.id: e for e in sg.entries_from(found, min_score=0.6)}
    assert set(entries) == {"strong", "exact"}
    assert entries["strong"].support[0].by == "auto"
    assert entries["exact"].support[0].by == "match"
    assert entries["strong"].support[0].units == [pool.loc.unit.id]


def test_pools_come_from_the_named_pages_and_sections(tmp_path):
    html = tmp_path / "w.html"
    html.write_text("<h1>One</h1><p>First.</p><h1>Two</h1><p>Second.</p>", encoding="utf-8")
    reg = SourceRegistry(
        Settings(wikibooks_html=html, sdm_pdf=tmp_path / "none.pdf"), tmp_path / "c"
    )
    assert [p.text for p in sg.build_pool(reg, ["wikibooks:Two"])] == ["Second."]
    assert [p.text for p in sg.build_pool(reg, ["wikibooks:*"])] == ["First.", "Second."]
    with pytest.raises(FileNotFoundError):
        sg.build_pool(reg, ["sdm:1-2"])
    with pytest.raises(ValueError):
        sg.parse_scope("sdm")


def test_the_pool_lists_a_repeated_sentence_once():
    a = sentence("If the LOCK prefix is used.", at=10)
    b = sentence("If the LOCK prefix is used.", at=11)

    class Reg:
        def __getitem__(self, _):
            class S:
                available = True
                label = "x"
                download = ""

                def units(self, at):
                    return [a.loc if at == 10 else b.loc]

            return S()

    pool = sg.build_pool(Reg(), ["sdm:10-11"])  # type: ignore[arg-type]
    assert len(pool) == 1
