import pytest

from docx86.config import Settings
from docx86.content import load_content
from docx86.embedding import HashEmbedder
from docx86.index import IndexStaleError, build_index, ensure_fresh, load_index, save_index
from docx86.main import build_engine


def test_exact_mnemonic_is_pinned_first(engine):
    hit = engine.search("popcnt")[0]
    assert (hit.slug, hit.match, hit.score) == ("popcnt", "mnemonic", 1.0)


def test_alias_resolves_to_canonical_page(engine):
    assert engine.search("SAL")[0].slug == "shl"


def test_semantic_ranking(engine):
    assert engine.search("count set bits", kind="instruction")[0].slug == "popcnt"
    assert engine.search("pointer arithmetic", kind="instruction")[0].slug == "lea"


def test_mnemonic_token_in_longer_query_boosts_but_does_not_pin(engine):
    hits = engine.search("what does lea do", kind="instruction")
    assert hits[0].slug == "lea" and hits[0].match == "mnemonic" and hits[0].score < 1.0


def test_kind_filter(engine):
    assert {h.kind for h in engine.search("registers", kind="article")} == {"article"}
    assert {h.kind for h in engine.search("registers", kind="instruction")} == {"instruction"}


def test_limit_and_empty_query(engine):
    assert len(engine.search("bits", limit=2)) == 2
    assert engine.search("   ") == []


def test_one_hit_per_page(engine):
    hits = engine.search("count the number of set bits population count", kind="instruction")
    assert len({(h.kind, h.slug) for h in hits}) == len(hits)


def test_index_roundtrip(tmp_path, content_dir):
    content, emb = load_content(content_dir), HashEmbedder()
    built = build_index(content, emb)
    save_index(built, tmp_path / "ix")
    loaded = load_index(tmp_path / "ix")
    assert loaded.units == built.units
    assert (loaded.vectors == built.vectors).all()
    ensure_fresh(loaded, content, emb)


def test_missing_index_is_stale(tmp_path):
    with pytest.raises(IndexStaleError):
        load_index(tmp_path / "nope")


def test_stale_index_detected_and_strict_mode_refuses_to_start(tmp_path, content_dir):
    s = Settings(
        content_dir=content_dir,
        index_dir=tmp_path / "ix",
        embedder="hash",
        rebuild_stale_index=True,
    )
    build_engine(s)  # builds a fresh index
    page = content_dir / "instructions" / "lea.md"
    page.write_text(page.read_text().replace("Does a thing.", "Does something else."))

    strict = s.model_copy(update={"rebuild_stale_index": False})
    with pytest.raises(IndexStaleError, match="content changed"):
        build_engine(strict)
    build_engine(s)  # dev mode rebuilds
    build_engine(strict)  # ...after which strict mode is happy


def test_index_built_with_other_embedder_is_rejected(tmp_path, content_dir):
    content = load_content(content_dir)
    index = build_index(content, HashEmbedder())
    index.embedder_id = "fastembed:something-else"
    with pytest.raises(IndexStaleError, match="something-else"):
        ensure_fresh(index, content, HashEmbedder())
