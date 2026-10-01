from pathlib import Path

import pytest

from conftest import ARTICLE, DEFAULT_PAGES, page_md, write_content
from docx86.content import ContentError, load_content, split_front_matter


def problems(root: Path) -> str:
    with pytest.raises(ContentError) as err:
        load_content(root)
    return str(err.value)


def test_loads_valid_content(content_dir):
    c = load_content(content_dir)
    assert set(c.instructions) == {"popcnt", "lea", "shl"}
    assert set(c.articles) == {"regs"}
    assert c.resolve("sal").slug == "shl"  # alias, case-insensitive
    assert c.resolve("POPCNT").slug == "popcnt"
    assert c.resolve("nothing") is None
    assert set(c.instructions["shl"].sections) == {
        "What it does",
        "When to use it",
        "Gotchas",
        "Example",
    }


def test_missing_required_section(tmp_path):
    root = write_content(tmp_path)
    secs = {"What it does": "x", "When to use it": "y", "Example": "```nasm\nnop\n```"}
    (root / "instructions" / "lea.md").write_text(
        page_md("lea", sections=secs, category="miscellaneous")
    )
    assert "missing or empty required section '## Gotchas'" in problems(root)


def test_example_needs_code_fence(tmp_path):
    root = write_content(tmp_path)
    secs = {"What it does": "x", "When to use it": "y", "Gotchas": "z", "Example": "just prose"}
    (root / "instructions" / "lea.md").write_text(
        page_md("lea", sections=secs, category="miscellaneous")
    )
    assert "must contain a fenced code block" in problems(root)


def test_h1_in_body_rejected(tmp_path):
    root = write_content(tmp_path)
    (root / "instructions" / "lea.md").write_text(
        page_md("lea", body_prefix="# Heading\n\n", category="miscellaneous")
    )
    assert "must not contain an H1" in problems(root)


def test_filename_must_match_slug(tmp_path):
    root = write_content(tmp_path)
    (root / "instructions" / "lea.md").rename(root / "instructions" / "other.md")
    assert "filename must equal slug" in problems(root)


def test_page_must_be_in_roster(tmp_path):
    root = write_content(tmp_path)
    (root / "instructions" / "mov.md").write_text(page_md("mov", category="data-transfer"))
    assert "mov: not in content/roster.yaml" in problems(root)


def test_alias_collision(tmp_path):
    pages = [*DEFAULT_PAGES, {"slug": "sal", "category": "shift-rotate"}]
    assert "collides with" in problems(write_content(tmp_path, pages))


def test_related_must_be_in_roster(tmp_path):
    pages = [{"slug": "lea", "category": "miscellaneous", "related": ("ghost",)}]
    assert "related 'ghost' is not a slug in content/roster.yaml" in problems(
        write_content(tmp_path, pages, extra_roster=())
    )


def test_schema_errors_are_all_reported(tmp_path):
    root = write_content(tmp_path)
    bad = page_md("lea", category="miscellaneous").replace(
        "category: miscellaneous", "category: nope"
    )
    bad = bad.replace("mnemonic: LEA", "mnemonic: lea")
    (root / "instructions" / "lea.md").write_text(bad)
    msg = problems(root)
    assert "category" in msg and "mnemonic" in msg  # both problems in one report


def test_search_phrases_minimum(tmp_path):
    pages = [{"slug": "lea", "category": "miscellaneous", "phrases": ("only one",)}]
    assert "search_phrases" in problems(write_content(tmp_path, pages, extra_roster=()))


def test_raw_html_in_markdown_is_escaped(tmp_path):
    root = write_content(tmp_path)
    secs = {
        "What it does": "<script>alert(1)</script>",
        "When to use it": "y",
        "Gotchas": "z",
        "Example": "```nasm\nnop\n```",
    }
    (root / "instructions" / "lea.md").write_text(
        page_md("lea", sections=secs, category="miscellaneous")
    )
    html = load_content(root).instructions["lea"].body_html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_article_validation(tmp_path):
    root = write_content(tmp_path, articles={"regs": ARTICLE.replace("popcnt", "ghost")})
    assert "related_instructions 'ghost'" in problems(root)


def test_missing_roster(tmp_path):
    (tmp_path / "instructions").mkdir()
    assert "roster.yaml: missing" in problems(tmp_path)


@pytest.mark.parametrize("text", ["no front matter", "---\nslug: x\n", "---\n- a\n- b\n---\nbody"])
def test_front_matter_errors(text):
    with pytest.raises(ValueError):
        split_front_matter(text)
