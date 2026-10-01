import pytest

from docx86 import wikibooks
from docx86.config import PROJECT_ROOT, get_settings

SAMPLE = """<html><head><title>x</title><style>.a{color:red}</style></head><body>
<h1><span class="mw-headline">Assemblers</span></h1>
<p>Intro &amp; overview.</p>
<h2><span class="mw-headline" id="NASM">Netwide Assembler (NASM)</span>
<span class="mw-editsection">[edit]</span></h2>
<p>NASM uses <b>Intel</b> syntax.</p>
<pre>section .text
global _start
_start:
    mov eax, 1</pre>
<div class="toc">Contents hidden chrome</div>
<h3>Hello World (Linux)</h3>
<ul><li>one</li><li>two</li></ul>
<script>var x = 1;</script>
</body></html>"""


def test_sections_follow_headings_and_drop_chrome():
    secs = {s.title: s for s in wikibooks.parse_sections(SAMPLE)}
    assert list(secs) == ["Assemblers", "Netwide Assembler (NASM)", "Hello World (Linux)"]
    assert [s.level for s in secs.values()] == [1, 2, 3]
    assert "Intro & overview." in secs["Assemblers"].text
    nasm = secs["Netwide Assembler (NASM)"].text
    assert "NASM uses Intel syntax." in nasm
    assert "[edit]" not in "".join(secs)  # the edit link is not part of the title
    assert "Contents hidden chrome" not in nasm and "var x" not in nasm


def test_pre_blocks_keep_their_line_breaks_and_indentation():
    text = {s.title: s.text for s in wikibooks.parse_sections(SAMPLE)}["Netwide Assembler (NASM)"]
    assert "section .text\nglobal _start\n_start:\n    mov eax, 1" in text


def test_find_matches_all_words_in_titles():
    secs = wikibooks.parse_sections(SAMPLE)
    assert [s.title for s in wikibooks.find(secs, "hello world")] == ["Hello World (Linux)"]
    assert [s.title for s in wikibooks.find(secs, "NASM")] == ["Netwide Assembler (NASM)"]
    assert wikibooks.find(secs, "nonexistent") == []


def test_grep_returns_a_snippet_per_section():
    secs = wikibooks.parse_sections(SAMPLE)
    (hit,) = wikibooks.grep(secs, "intel syntax")
    assert hit[0].title == "Netwide Assembler (NASM)" and "Intel syntax" in hit[1]


def test_cache_roundtrip_and_invalidation(tmp_path):
    page = tmp_path / "w.html"
    page.write_text(SAMPLE, encoding="utf-8")
    first = wikibooks.load_sections(page, tmp_path / "cache")
    assert (tmp_path / "cache" / "wikibooks_sections.json").exists()
    assert wikibooks.load_sections(page, tmp_path / "cache") == first
    page.write_text(
        SAMPLE.replace("Hello World (Linux)", "Hello World (Windows)"), encoding="utf-8"
    )
    assert "Hello World (Windows)" in [
        s.title for s in wikibooks.load_sections(page, tmp_path / "cache")
    ]


def test_missing_file_explains_how_to_download(tmp_path):
    with pytest.raises(SystemExit) as err:
        wikibooks.load_sections(tmp_path / "nope.html", tmp_path)
    assert "wget" in str(err.value)


@pytest.mark.skipif(
    not get_settings().wikibooks_html.exists(), reason="Wikibooks file not downloaded"
)
def test_real_file_has_the_sections_the_articles_cite():
    secs = wikibooks.load_sections(get_settings().wikibooks_html, PROJECT_ROOT / ".cache")
    titles = {s.title for s in secs}
    for needed in ("Netwide Assembler (NASM)", "Hello World (Linux)", "Loop Instructions"):
        assert needed in titles, needed
