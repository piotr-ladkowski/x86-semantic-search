"""Keep docs and code honest: the page template in the guide must satisfy the real schema."""

import re

from docx86.config import PROJECT_ROOT
from docx86.content import split_front_matter, split_sections
from docx86.models import InstructionMeta

GUIDE = (PROJECT_ROOT / "docs" / "CONTENT_GUIDE.md").read_text(encoding="utf-8")


def template() -> str:
    m = re.search(r"^## Template\n\n````markdown\n(.*?)\n````", GUIDE, re.S | re.M)
    assert m, "CONTENT_GUIDE.md must contain a ````markdown template under '## Template'"
    return m.group(1)


def test_guide_template_is_valid_against_the_schema():
    front, body = split_front_matter(template())
    meta = InstructionMeta.model_validate(front)
    assert meta.slug == "example"
    sections, problems = split_sections(body)
    assert not problems
    assert list(sections) == ["What it does", "When to use it", "Gotchas", "Example"]


def test_guide_lists_every_front_matter_field():
    for field in InstructionMeta.model_fields:
        assert f"`{field}`" in GUIDE, f"CONTENT_GUIDE.md does not document `{field}`"


def test_architecture_lists_every_setting():
    from docx86.config import Settings

    doc = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for name in Settings.model_fields:
        assert f"`DOCX86_{name.upper()}`" in doc, (
            f"ARCHITECTURE.md does not document DOCX86_{name.upper()}"
        )
