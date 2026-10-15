from docx86.scope import SCOPE_WORDS, scope_hint


def test_scope_hint_names_the_first_out_of_scope_word():
    hint = scope_hint("add two packed floats in XMM registers")
    assert (hint.word, hint.about) == ("packed", "packed (vector) data")
    assert scope_hint("load a double into xmm0").about == "SSE/AVX vector registers"
    assert scope_hint("read the cr3 register").about == "control registers (ring 0)"
    assert scope_hint("sine of st0").about == "x87 floating point"


def test_scope_hint_ignores_in_scope_queries():
    for q in ("double a number", "count bits in a bit vector", "add two integers", "", "xmmx"):
        assert scope_hint(q) is None, q


def test_scope_words_are_lowercase_tokens():
    assert all(w == w.lower() and w.isalnum() for w in SCOPE_WORDS)
