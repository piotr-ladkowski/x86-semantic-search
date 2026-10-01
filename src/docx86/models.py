"""Content schema. docs/CONTENT_GUIDE.md is the human/LLM-readable description of these models."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MNEMONIC_RE = re.compile(r"^[A-Z][A-Z0-9]*$")


class Category(StrEnum):
    """Mirrors the subsection groups of Intel SDM Vol. 1 §5.1 (General-Purpose Instructions)."""

    DATA_TRANSFER = "data-transfer"
    BINARY_ARITHMETIC = "binary-arithmetic"
    LOGICAL = "logical"
    SHIFT_ROTATE = "shift-rotate"
    BIT_BYTE = "bit-byte"
    CONTROL_TRANSFER = "control-transfer"
    STRING = "string"
    FLAG_CONTROL = "flag-control"
    MISCELLANEOUS = "miscellaneous"
    RANDOM_NUMBER = "random-number"
    BMI = "bmi"

    @property
    def label(self) -> str:
        return CATEGORY_LABELS[self]


CATEGORY_LABELS: dict[Category, str] = {
    Category.DATA_TRANSFER: "Data transfer",
    Category.BINARY_ARITHMETIC: "Binary arithmetic",
    Category.LOGICAL: "Logical",
    Category.SHIFT_ROTATE: "Shift & rotate",
    Category.BIT_BYTE: "Bit & byte",
    Category.CONTROL_TRANSFER: "Control transfer",
    Category.STRING: "String",
    Category.FLAG_CONTROL: "Flag control",
    Category.MISCELLANEOUS: "Miscellaneous",
    Category.RANDOM_NUMBER: "Random number",
    Category.BMI: "BMI1 / BMI2",
}


class Status(StrEnum):
    DRAFT = "draft"  # written (usually by an LLM) and checked against the SDM, not human-reviewed
    REVIEWED = "reviewed"  # a human has read it against the SDM


Flag = Literal["CF", "PF", "AF", "ZF", "SF", "DF", "OF"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlagEffects(_Model):
    """Effect on RFLAGS status flags. Omit a flag everywhere = the instruction leaves it alone."""

    modified: list[Flag] = Field(
        default_factory=list, description="Set, cleared or computed from the result."
    )
    undefined: list[Flag] = Field(default_factory=list, description="Architecturally undefined.")
    read: list[Flag] = Field(default_factory=list, description="Consumed as an input.")
    note: str | None = Field(
        default=None, description="Anything the lists cannot say (e.g. 'only if count != 0')."
    )

    @property
    def is_empty(self) -> bool:
        return not (self.modified or self.undefined or self.read)


class Form(_Model):
    """One encodable form, restricted to forms valid in 64-bit mode."""

    syntax: str = Field(description="Intel syntax, as in the SDM: 'ADD r/m64, r64'.")
    opcode: str = Field(description="Opcode column from the SDM: 'REX.W + 01 /r'.")
    note: str | None = None


class InstructionMeta(_Model):
    slug: str
    mnemonic: str = Field(description="Primary mnemonic, uppercase, as the SDM spells it.")
    aliases: list[str] = Field(default_factory=list, description="Other mnemonics for this page.")
    title: str = Field(description="Short human name: 'Add', 'Load Effective Address'.")
    summary: str = Field(max_length=160, description="One sentence shown in search results.")
    category: Category
    status: Status = Status.DRAFT
    cpuid_feature: str | None = Field(
        default=None, description="CPUID feature needed ('POPCNT', 'BMI2'); null = baseline x86-64."
    )
    sdm_entries: list[str] = Field(
        min_length=1,
        description="Exact SDM Vol. 2 outline titles this page was verified against.",
    )
    extra_sources: list[str] = Field(
        default_factory=list, description="Citations for any claim that is not in the SDM."
    )
    flags: FlagEffects = Field(default_factory=FlagEffects)
    forms: list[Form] = Field(min_length=1)
    search_phrases: list[str] = Field(
        min_length=3,
        description="Natural-language queries this instruction should be the answer to.",
    )
    related: list[str] = Field(default_factory=list, description="Slugs of related instructions.")

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError("slug must be lowercase letters/digits separated by single hyphens")
        return v

    @field_validator("mnemonic", "aliases")
    @classmethod
    def _mnemonic_case(cls, v: str | list[str]) -> str | list[str]:
        for m in [v] if isinstance(v, str) else v:
            if not MNEMONIC_RE.match(m):
                raise ValueError(f"mnemonic {m!r} must be uppercase (e.g. 'ADD', 'INT3')")
        return v

    @field_validator("search_phrases")
    @classmethod
    def _phrases(cls, v: list[str]) -> list[str]:
        if any(not p.strip() or len(p) > 120 for p in v):
            raise ValueError("search_phrases must be non-empty and at most 120 chars each")
        return v


class Instruction(InstructionMeta):
    body_md: str
    body_html: str
    sections: dict[str, str] = Field(description="H2 heading -> markdown, in order.")

    @property
    def all_mnemonics(self) -> list[str]:
        return [self.mnemonic, *self.aliases]


class ArticleMeta(_Model):
    slug: str
    title: str
    summary: str = Field(max_length=200)
    tags: list[str] = Field(default_factory=list)
    status: Status = Status.DRAFT
    related_instructions: list[str] = Field(default_factory=list)
    sdm_refs: list[str] = Field(
        default_factory=list, description="SDM sections/pages the article was verified against."
    )
    extra_sources: list[str] = Field(default_factory=list)
    search_phrases: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError("slug must be lowercase letters/digits separated by single hyphens")
        return v


class Article(ArticleMeta):
    body_md: str
    body_html: str


# ----- roster: the list of instructions that are in scope (drives progress tracking) -----


class RosterEntry(_Model):
    slug: str
    mnemonic: str
    category: Category
    sdm: list[str] = Field(min_length=1, description="Exact SDM outline titles.")
    note: str | None = None


class DeferredEntry(_Model):
    mnemonics: list[str]
    reason: str


class ExcludedEntry(_Model):
    reason: Literal[
        "invalid-in-64-bit-mode",
        "privileged",
        "segmentation",
        "non-scalar-or-non-integer",
        "extended-state",
    ]
    mnemonics: list[str]
    note: str | None = None


class Roster(_Model):
    sdm_revision: str
    instructions: list[RosterEntry]
    deferred: list[DeferredEntry] = Field(default_factory=list)
    excluded: list[ExcludedEntry] = Field(default_factory=list)
