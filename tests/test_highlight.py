import re

import pytest

from conftest import page_md, write_content
from docx86.config import PROJECT_ROOT
from docx86.content import load_content
from docx86.highlight import highlight_code

# Pygments classes that the stylesheet intentionally leaves unstyled.
UNSTYLED = {"w", "nv"}


def classes(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<span class="([a-z0-9]+)">([^<]*)</span>', html)


def test_instructions_registers_numbers_labels_and_comments_get_distinct_classes():
    got = dict(
        (text, cls) for cls, text in classes(highlight_code("loop: mov rax, 16 ; go", "nasm"))
    )
    assert got["mov"] == "nf" and got["rax"] == "nb" and got["16"] == "mi"
    assert got["loop:"] == "nl" and got["; go"] == "c1"


@pytest.mark.parametrize("code", ["rep movsb", "repne scasb", "lock add qword [rdi], 1"])
def test_instruction_after_a_prefix_is_still_an_instruction(code):
    got = dict((text, cls) for cls, text in classes(highlight_code(code, "nasm")))
    prefix, instruction = code.split()[:2]
    assert got[prefix] == "nf" and got[instruction] == "nf"


def test_directives_are_keywords_not_instructions():
    got = dict(
        (text, cls)
        for cls, text in classes(highlight_code("default rel\nmsglen: equ $ - msg", "nasm"))
    )
    assert got["default"] == "k" and got["equ"] == "k"


def test_asm_alias_means_intel_syntax_not_gas():
    code = "mov rax, [rdi]"
    assert highlight_code(code, "asm") == highlight_code(code, "nasm")


@pytest.mark.parametrize("lang", ["", "klingon", "   "])
def test_unknown_or_missing_language_falls_back_to_plain(lang):
    assert highlight_code("mov rax, 1", lang) == ""


def test_code_is_html_escaped():
    html = highlight_code("mov eax, 1 ; <script>alert(1)</script> & done", "nasm")
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp;" in html


def test_markdown_fences_are_highlighted_and_other_fences_stay_plain(tmp_path):
    secs = {
        "What it does": "x",
        "When to use it": "y",
        "Gotchas": "z",
        "Example": "```nasm\nmov rax, rbx   ; copy\n```\n\n```text\nmov rax, rbx <b>\n```",
    }
    root = write_content(
        tmp_path / "c",
        pages=[{"slug": "lea", "category": "miscellaneous"}],
        articles={},
        extra_roster=(),
    )
    (root / "instructions" / "lea.md").write_text(
        page_md("lea", sections=secs, category="miscellaneous")
    )
    html = load_content(root).instructions["lea"].body_html
    assert '<code class="language-nasm">' in html and '<span class="nf">mov</span>' in html
    assert (
        '<code class="language-text">mov rax, rbx &lt;b&gt;' in html
    )  # unknown language: escaped, no spans


def test_every_token_class_in_real_content_is_styled():
    real = load_content(PROJECT_ROOT / "content")
    used: set[str] = set()
    for item in [*real.instructions.values(), *real.articles.values()]:
        for block in re.findall(r"<pre><code[^>]*>(.*?)</code></pre>", item.body_html, re.S):
            used |= {cls for cls, _ in classes(block)}
    css = (PROJECT_ROOT / "assets" / "app.css").read_text(encoding="utf-8")
    styled = set(re.findall(r"\.prose pre code \.([a-z0-9]+)", css))
    missing = used - styled - UNSTYLED
    assert not missing, f"add a rule in assets/app.css for Pygments classes: {sorted(missing)}"


def test_every_assembly_fence_in_real_content_is_actually_highlighted():
    real = load_content(PROJECT_ROOT / "content")
    for item in [*real.instructions.values(), *real.articles.values()]:
        for block in re.findall(
            r'<pre><code class="language-nasm">(.*?)</code></pre>', item.body_html, re.S
        ):
            assert '<span class="nf">' in block, (
                f"{item.slug}: a nasm block has no instructions coloured"
            )
