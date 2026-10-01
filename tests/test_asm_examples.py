"""Articles may only show long assembly listings that exist in tests/asm.

Those are the programs `make verify-asm` assembles and runs. This test is the fast, Docker-free half
of that guarantee: it cannot run the code, but it stops a listing from drifting away from (or never
having come from) the tested source.
"""

import re

from docx86.config import PROJECT_ROOT

ASM_DIR = PROJECT_ROOT / "tests" / "asm"
ARTICLES = PROJECT_ROOT / "content" / "articles"
MIN_LINES = 5  # shorter snippets are illustrations; longer ones must be tested programs


def code_lines(text: str) -> list[str]:
    """Instruction/label lines with comments and surrounding whitespace removed."""
    lines = (re.sub(r"\s+", " ", line.split(";")[0]).strip() for line in text.splitlines())
    return [line for line in lines if line]


def lines_in_tested_programs() -> set[str]:
    return {
        line for f in ASM_DIR.glob("*.asm") for line in code_lines(f.read_text(encoding="utf-8"))
    }


def test_the_tested_programs_exist():
    names = {f.name for f in ASM_DIR.glob("*.asm")}
    assert {"hello.asm", "hello_libc.asm", "hello_win.asm", "hello_win32.asm"} <= names
    assert (ASM_DIR / "run.sh").exists() and (ASM_DIR / "Dockerfile").exists()


def test_long_article_listings_come_from_tested_programs():
    tested = lines_in_tested_programs()
    problems = []
    for article in sorted(ARTICLES.glob("*.md")):
        for block in re.findall(r"```nasm\n(.*?)```", article.read_text(encoding="utf-8"), re.S):
            lines = code_lines(block)
            if len(lines) < MIN_LINES:
                continue
            missing = [line for line in lines if line not in tested]
            if missing:
                problems.append(f"{article.name}: not in tests/asm: {missing[:4]}")
    assert not problems, (
        "Listings of 5+ lines in articles must be copied from a program in tests/asm "
        "(add it there and run `make verify-asm`):\n" + "\n".join(problems)
    )
