"""Out-of-scope hints for search queries.

The relevance floor cannot tell an x86 question that is out of scope ("add two packed floats in
xmm registers") from one that is in scope: both score about as high against some page (measured
2026-10-08: such queries reach 0.80-0.88 against ADD or MOV, above many genuine matches). What
*does* give them away is vocabulary, so a query containing one of these words gets a short notice
naming the word and the family it points at. The list is deliberately short and literal: a word
goes in only if it almost never appears in a question about a scalar integer instruction
("double" and "vector" do not qualify: "double a number", "bit vector").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VECTOR_REGISTERS = [f"{r}{i}" for r in ("xmm", "ymm", "zmm") for i in ["", *range(32)]]

# word (lowercase token) -> what the visitor is probably after; see docs/SCOPE.md "Not in v1".
SCOPE_WORDS: dict[str, str] = {
    **dict.fromkeys(_VECTOR_REGISTERS, "SSE/AVX vector registers"),
    **dict.fromkeys(("sse", "sse2", "sse3", "ssse3", "sse4"), "SSE vector instructions"),
    **dict.fromkeys(("avx", "avx2", "avx512"), "AVX vector instructions"),
    "simd": "SIMD (vector) instructions",
    "packed": "packed (vector) data",
    "mmx": "MMX",
    "amx": "AMX",
    **dict.fromkeys(("x87", "fpu", *[f"st{i}" for i in range(8)]), "x87 floating point"),
    **dict.fromkeys(("float", "floats", "floating"), "floating-point arithmetic"),
    "msr": "model-specific registers (ring 0)",
    **dict.fromkeys(("cr0", "cr2", "cr3", "cr4", "cr8"), "control registers (ring 0)"),
    **dict.fromkeys(("gdt", "idt", "ldt", "tss"), "descriptor tables (ring 0)"),
    "paging": "paging (ring 0)",
}


@dataclass(frozen=True)
class ScopeHint:
    word: str  # as it appeared in the query (lowercased)
    about: str  # the out-of-scope family that word points at


def scope_hint(query: str) -> ScopeHint | None:
    """The first out-of-scope word in `query`, or None."""
    for tok in re.findall(r"[A-Za-z0-9]+", query.lower()):
        if (about := SCOPE_WORDS.get(tok)) is not None:
            return ScopeHint(tok, about)
    return None
