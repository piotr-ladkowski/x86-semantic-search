"""Sentence splitting and fingerprints: what evidence ledgers are keyed by."""

import pytest

from docx86.textunits import digest, split_sentences, squash, tidy


def test_digest_ignores_case_spacing_punctuation_and_markdown():
    a = "Counts the bits set to `1`, in the *source*."
    b = "counts  the bits set to 1 in the source"
    assert digest(a) == digest(b) and len(digest(a)) == 10


def test_digest_changes_when_a_word_changes():
    assert digest("Adds the source.") != digest("Adds the destination.")
    assert digest("CF is set") != digest("CF is not set")


def test_squash_keeps_only_letters_and_digits():
    assert squash("REX.W + 01 /r") == "rexw01r"
    assert squash("r/m8¹") == squash("r/m81")  # NFKC: superscript one is a plain one


def test_tidy_normalises_quotes_hyphens_and_spaces():
    assert tidy("a­  b “q”  it’s") == 'a b "q" it\'s'


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("One. Two. Three.", ["One.", "Two.", "Three."]),
        ("Is it? Yes! Done.", ["Is it?", "Yes!", "Done."]),
        # abbreviations and initials do not end a sentence
        ("Flags, e.g. CF and ZF. Next one.", ["Flags, e.g. CF and ZF.", "Next one."]),
        ("See Vol. 2 for details. Then stop.", ["See Vol. 2 for details.", "Then stop."]),
        ("Written by J. Smith. Reviewed later.", ["Written by J. Smith.", "Reviewed later."]),
        # a lower-case continuation is not a new sentence
        ("It is version 1.5 of the spec. Fine.", ["It is version 1.5 of the spec.", "Fine."]),
        ("Use x.y here and move on.", ["Use x.y here and move on."]),
    ],
)
def test_split_sentences(text, expected):
    assert split_sentences(text) == expected


def test_code_spans_and_links_are_never_split():
    text = "Run `a. B` now. See [the guide. Part 2](/articles/x). Done."
    assert split_sentences(text) == [
        "Run `a. B` now.",
        "See [the guide. Part 2](/articles/x).",
        "Done.",
    ]


def test_a_sentence_may_start_with_a_code_span_or_bold_text():
    text = "**32-bit operations zero the upper half.** `add eax, ebx` clears bits 63:32."
    assert split_sentences(text) == [
        "**32-bit operations zero the upper half.**",
        "`add eax, ebx` clears bits 63:32.",
    ]


def test_a_list_number_is_not_a_sentence():
    assert split_sentences("1. If the class is MEMORY, pass it on the stack.") == [
        "1. If the class is MEMORY, pass it on the stack."
    ]
    # ... but a number that ends a real sentence still splits
    assert split_sentences("The count is at most 64. The next sentence.") == [
        "The count is at most 64.",
        "The next sentence.",
    ]


def test_empty_and_whitespace_input():
    assert split_sentences("") == [] and split_sentences("  \n ") == []
