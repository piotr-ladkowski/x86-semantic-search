"""Sentence splitting and fingerprints: the shared primitives of the evidence ledger.

A *unit* is a sentence of prose, a table row or a code block. Evidence refers to units by a
fingerprint (`digest`) rather than by position or by quoting them, for two reasons:

  * a fingerprint changes when the unit's wording changes, so evidence cannot silently go stale;
  * a fingerprint reveals nothing about a copyrighted source, so the repository can point at a
    sentence of the Intel manual without republishing it.

Recording evidence and checking it both go through the functions here, so they cannot disagree.
Changing `squash` or `split_sentences` changes fingerprints: bump SPLITTER_VERSION and re-lock.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

SPLITTER_VERSION = 1

# Words after which a full stop does not end a sentence.
ABBREVIATIONS = {
    "e.g.", "i.e.", "etc.", "vs.", "cf.", "fig.", "approx.", "vol.", "sec.", "ch.", "no.", "incl.",
    "resp.", "viz.", "al.",
}  # fmt: skip

_PROTECTED = re.compile(r"`[^`]*`|\[[^\]]*\]\([^)]*\)")  # code spans and markdown links
_BOUNDARY = re.compile(r"(?<=[.!?])([\"')\]*_”’]*)\s+")
_STARTS_SENTENCE = re.compile(r"[A-Z0-9(\[`*\"#•“\u0000]")  # \u0000: a hidden code span or link


def squash(text: str) -> str:
    """Lower-case letters and digits only (ignores spacing, punctuation, hyphens and markdown)."""
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def digest(text: str) -> str:
    """10-hex-character fingerprint of a unit's wording."""
    return hashlib.sha1(squash(text).encode()).hexdigest()[:10]


def tidy(text: str) -> str:
    """Readable single-line form of extracted text (soft hyphens, odd quotes, runs of spaces)."""
    text = unicodedata.normalize("NFKC", text).replace("­", "")
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    """Split a paragraph into sentences. Code spans and links are never split."""
    text = text.strip()
    if not text:
        return []
    vault: list[str] = []

    def hide(m: re.Match[str]) -> str:
        vault.append(m.group(0))
        return f"\u0000{len(vault) - 1}\u0000"

    hidden = _PROTECTED.sub(hide, text)
    pieces: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(hidden):
        before = hidden[start : m.start()]
        last_word = before.rsplit(None, 1)[-1].lower() if before.split() else ""
        after = hidden[m.end() :]
        if last_word in ABBREVIATIONS or not after or not _STARTS_SENTENCE.match(after):
            continue
        if re.fullmatch(r"[A-Z]\.", before.rsplit(None, 1)[-1] if before.split() else ""):
            continue  # an initial such as "J."
        if re.fullmatch(r"\d{1,2}\.", before.strip()):
            continue  # a list number opening the piece ("2. If the class is ..."), not a sentence
        pieces.append(hidden[start : m.end() - len(m.group(0)) + len(m.group(1))].strip())
        start = m.end()
    pieces.append(hidden[start:].strip())

    def restore(s: str) -> str:
        return re.sub(r"\u0000(\d+)\u0000", lambda m: vault[int(m.group(1))], s)

    return [restore(p) for p in pieces if p]
