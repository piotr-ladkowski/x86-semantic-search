"""Server-side syntax highlighting for fenced code blocks (Pygments; no JavaScript on the page).

Pygments emits `<span class="nf">...</span>` style markup; the colours live in assets/app.css.
Code blocks are always dark (`prose-pre:bg-zinc-900`), so one palette serves both the light and
the dark theme.

The stock NASM lexer needs two corrections that matter for our content:
  * It treats only the first word of a line as an instruction, so in `rep movsb` or `lock add`
    the real instruction after the prefix would be coloured as a plain symbol.
  * It colours directives such as `equ` and `default` like instructions.
"""

from __future__ import annotations

from collections.abc import Iterable

from pygments import highlight
from pygments.filter import Filter
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.token import Keyword, Name, _TokenType
from pygments.util import ClassNotFound

# Fence names that mean "x86 assembly in Intel syntax". (Pygments maps `asm` to the AT&T GAS lexer.)
ASM_LANGUAGES = {"nasm", "asm", "x86", "x86asm", "intel"}
PREFIXES = {
    "rep",
    "repe",
    "repz",
    "repne",
    "repnz",
    "lock",
    "xacquire",
    "xrelease",
    "bnd",
    "notrack",
}
DIRECTIVES = {
    "equ",
    "default",
    "bits",
    "align",
    "alignb",
    "times",
    "org",
    "incbin",
    "cpu",
    "absolute",
}

_FORMATTER = HtmlFormatter(nowrap=True)


class _NasmFixups(Filter):
    def filter(
        self, lexer: object, stream: Iterable[tuple[_TokenType, str]]
    ) -> Iterable[tuple[_TokenType, str]]:
        after_prefix = False
        for ttype, value in stream:
            word = value.strip().lower()
            if not word:  # whitespace between a prefix and its instruction keeps the state
                yield ttype, value
                continue
            was_prefix = ttype is Name.Function and word in PREFIXES
            if ttype is Name.Function and word in DIRECTIVES:
                ttype = Keyword
            elif after_prefix and ttype is Name.Variable:
                ttype = Name.Function
            after_prefix = was_prefix
            yield ttype, value


def highlight_code(code: str, lang: str) -> str:
    """HTML for the inside of a fenced block, or '' to fall back to plain escaped text."""
    name = lang.strip().lower()
    if not name:
        return ""
    is_asm = name in ASM_LANGUAGES
    try:
        lexer = get_lexer_by_name("nasm" if is_asm else name)
    except ClassNotFound:
        return ""
    if is_asm:
        lexer.add_filter(_NasmFixups())
    return highlight(code, lexer, _FORMATTER)
