"""A page is broken into claims: sentences, table rows, code blocks and structured facts."""

from conftest import write_content
from docx86.claims import claims_for_article, claims_for_instruction, claims_from_markdown
from docx86.content import load_content
from docx86.textunits import digest

MD = """\
Intro one. Intro two.

## Gotchas

- **Bold lead.** Detail with `code. Inside`.
- Plain bullet.

| Form | Opcode |
|------|--------|
| `ADD r/m64, r64` | `REX.W + 01 /r` |

```nasm
nop
```
"""


def test_prose_is_split_into_sentences_with_their_section():
    claims = claims_from_markdown(MD, "Introduction")
    prose = [(c.section, c.text) for c in claims if c.kind == "prose"]
    assert prose == [
        ("Introduction", "Intro one."),
        ("Introduction", "Intro two."),
        ("Gotchas", "**Bold lead.**"),
        ("Gotchas", "Detail with `code. Inside`."),
        ("Gotchas", "Plain bullet."),
    ]


def test_table_rows_and_code_blocks_are_claims():
    claims = claims_from_markdown(MD, "Introduction")
    (row,) = [c for c in claims if c.kind == "row"]
    assert row.text == "`ADD r/m64, r64` | `REX.W + 01 /r`" and row.header == ("Form", "Opcode")
    (code,) = [c for c in claims if c.kind == "code"]
    assert code.text == "nop"


def test_ids_are_fingerprints_of_the_wording():
    for c in claims_from_markdown(MD, "x"):
        assert c.id == digest(c.text)


def test_repeated_sentences_count_once():
    claims = claims_from_markdown("Same.\n\nSame.\n", "x")
    assert [c.text for c in claims] == ["Same."]


def test_instruction_front_matter_becomes_claims(content_dir):
    ins = load_content(content_dir).instructions["shl"]
    facts = {c.text: c.section for c in claims_for_instruction(ins) if c.kind == "fact"}
    assert facts["Summary of SHL."] == "Summary"
    assert facts["Also written as `SAL`."] == "Aliases"
    assert facts["`SHL r64, r/m64` is encoded as `REX.W + 00 /r`."] == "Forms"


def test_cpuid_requirement_is_a_claim(tmp_path):
    root = write_content(tmp_path / "c", [{"slug": "popcnt", "category": "bit-byte"}])
    path = root / "instructions" / "popcnt.md"
    path.write_text(
        path.read_text().replace("status: draft", "status: draft\ncpuid_feature: POPCNT")
    )
    ins = load_content(root).instructions["popcnt"]
    texts = [c.text for c in claims_for_instruction(ins)]
    assert "Needs the POPCNT CPU feature (reported by CPUID)." in texts


def test_titles_and_search_phrases_are_not_claims(content_dir):
    ins = load_content(content_dir).instructions["popcnt"]
    texts = " ".join(c.text for c in claims_for_instruction(ins))
    assert "Title of POPCNT" not in texts and "count the number of set bits" not in texts


def test_article_claims(content_dir):
    art = load_content(content_dir).articles["regs"]
    assert [(c.section, c.text) for c in claims_for_article(art)] == [
        ("Summary", "How registers behave."),
        ("Introduction", "Registers hold values."),
        ("Detail", "More detail."),
    ]
