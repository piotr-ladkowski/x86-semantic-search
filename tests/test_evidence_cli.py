"""`docx86 evidence ...` end to end, on a small content directory and a tiny source document."""

import pytest
import yaml

from docx86 import cli
from docx86.textunits import digest

SOURCE_HTML = """<html><body><h1>Population count</h1>
<p>The instruction counts the bits set to 1. It stores the count in a register.</p></body></html>"""
COUNTS = digest("The instruction counts the bits set to 1.")


@pytest.fixture
def env(tmp_path, content_dir, monkeypatch):
    html = tmp_path / "w.html"
    html.write_text(SOURCE_HTML, encoding="utf-8")
    for key, value in {
        "CONTENT_DIR": content_dir,
        "INDEX_DIR": tmp_path / "index",
        "EMBEDDER": "hash",
        "WIKIBOOKS_HTML": html,
        "SDM_PDF": tmp_path / "none.pdf",
        "SYSV_ABI_PDF": tmp_path / "none1.pdf",
        "MS_CALLING_CONVENTION_HTML": tmp_path / "none2.html",
        "MS_STACK_USAGE_HTML": tmp_path / "none3.html",
        "CACHE_DIR": tmp_path / "cache",
    }.items():
        monkeypatch.setenv(f"DOCX86_{key}", str(value))
    monkeypatch.chdir(tmp_path)  # no stray .env
    return content_dir


def run(capsys, *argv):
    code = cli.main(["evidence", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def cite_summary(capsys):
    args = (
        "cite",
        "popcnt",
        "1",
        "--doc",
        "wikibooks",
        "--at",
        "Population count",
        "--unit",
        COUNTS,
    )
    return run(capsys, *args)


def ledger(env):
    return yaml.safe_load((env / "evidence" / "instructions" / "popcnt.yaml").read_text())


def test_status_lists_every_page_with_its_coverage(env, capsys):
    code, out, _ = run(capsys, "status")
    assert code == 0
    assert "popcnt" in out and "regs (article)" in out and "6 unverified" in out
    assert "0 claims" not in out and "rest on a source sentence" in out


def test_cite_records_a_pointer_after_looking_the_sentence_up(env, capsys):
    code, out, _ = run(
        capsys, "cite", "popcnt", "1", "--doc", "wikibooks", "--at", "Population count",
        "--grep", "counts the bits", "--note", "says so",
    )  # fmt: skip
    assert code == 0 and "cited 1 sentence" in out and "counts the bits set to 1" in out
    (entry,) = ledger(env)["claims"]
    assert entry["support"][0]["units"] == [COUNTS] and entry["support"][0]["note"] == "says so"
    assert entry["gist"] == "Summary of POPCNT."


def test_cite_refuses_a_sentence_that_is_not_there(env, capsys):
    with pytest.raises(SystemExit) as err:
        run(capsys, "cite", "popcnt", "1", "--doc", "wikibooks", "--at", "Population count",
            "--unit", "0000000000")  # fmt: skip
    assert "no such sentence" in str(err.value)
    assert not (env / "evidence").exists()


def test_cite_refuses_a_document_that_is_missing(env, capsys):
    with pytest.raises(SystemExit) as err:
        run(capsys, "cite", "popcnt", "1", "--doc", "sdm", "--at", "5", "--unit", COUNTS)
    assert "not available here" in str(err.value)


def test_mark_classifies_claims_and_validates_arguments(env, capsys):
    code, out, _ = run(capsys, "mark", "popcnt", "3", "4", "--as", "editorial", "--note", "advice")
    assert code == 0 and "marked 2 claim(s) as editorial" in out
    assert [e["how"] for e in ledger(env)["claims"]] == ["editorial", "editorial"]
    for argv, message in (
        (("mark", "popcnt", "1", "--as", "derived"), "needs --note"),
        (("mark", "popcnt", "1", "--as", "run"), "needs --ref"),
    ):
        with pytest.raises(SystemExit) as err:
            run(capsys, *argv)
        assert message in str(err.value)


def test_show_prints_the_cited_passage(env, capsys):
    run(
        capsys,
        "cite",
        "popcnt",
        "1",
        "--doc",
        "wikibooks",
        "--at",
        "Population count",
        "--unit",
        COUNTS,
    )
    code, out, _ = run(capsys, "show", "popcnt")
    assert code == 0 and "► The instruction counts the bits set to 1." in out
    assert "  It stores the count in a register." in out  # context, not marked


def test_find_lists_units_and_sections(env, capsys):
    code, out, _ = run(capsys, "find", "wikibooks")
    assert code == 0 and out.strip() == "Population count"
    code, out, _ = run(capsys, "find", "wikibooks", "Population count", "--grep", "stores")
    assert code == 0 and digest("It stores the count in a register.") in out
    code, _, err = run(capsys, "find", "wikibooks", "Population count", "--grep", "zzz")
    assert code == 1 and "no matching sentence" in err
    code, _, err = run(capsys, "find", "sdm", "1")
    assert code == 1 and "not available here" in err


def test_check_passes_then_fails_when_a_claim_is_reworded(env, capsys):
    run(
        capsys,
        "cite",
        "popcnt",
        "1",
        "--doc",
        "wikibooks",
        "--at",
        "Population count",
        "--unit",
        COUNTS,
    )
    code, out, _ = run(capsys, "check")
    assert code == 0 and out.startswith("OK:") and "1 source pointers confirmed" in out
    page = env / "instructions" / "popcnt.md"
    page.write_text(page.read_text().replace("Summary of POPCNT.", "Another summary."))
    code, out, err = run(capsys, "check")
    assert code == 1 and "no longer exists" in err and out.startswith("FAILED:")


def test_suggest_prints_candidates_and_writes_only_strong_ones(env, capsys):
    scope = ("--scope", "wikibooks:Population count")
    code, out, _ = run(capsys, "suggest", "popcnt", *scope)
    assert code == 0 and "similar" in out and "The instruction counts" in out
    code, out, _ = run(capsys, "suggest", "popcnt", *scope, "--write", "--min", "0.99")
    assert code == 0 and "recorded 0 exact and 0 suggested" in out
    assert not (env / "evidence").exists()
    code, out, _ = run(capsys, "suggest", "popcnt", *scope, "--write", "--min", "0.0")
    assert code == 0 and "suggested links" in out
    assert all(s["by"] == "auto" for e in ledger(env)["claims"] for s in e["support"])


def test_suggest_needs_a_scope_for_articles_and_a_slug(env, capsys):
    code, _, err = run(capsys, "suggest", "regs")
    assert code == 0 and "give --scope" in err
    with pytest.raises(SystemExit):
        run(capsys, "suggest")
    with pytest.raises(SystemExit):
        run(capsys, "suggest", "--all")


def test_unknown_pages_are_reported(env, capsys):
    with pytest.raises(SystemExit) as err:
        run(capsys, "show", "nope")
    assert "No unique page" in str(err.value)


def test_retarget_moves_evidence_to_the_reworded_claim(env, capsys):
    cite_summary(capsys)
    old_id = ledger(env)["claims"][0]["id"]
    page = env / "instructions" / "popcnt.md"
    page.write_text(page.read_text().replace("Summary of POPCNT.", "Another summary."))
    code, _, err = run(capsys, "check")
    assert code == 1 and "retarget" in err
    code, out, _ = run(capsys, "retarget", "popcnt", old_id[:6], "1")
    assert code == 0 and "Re-read" in out
    (entry,) = ledger(env)["claims"]
    assert entry["id"] != old_id and entry["gist"] == "Another summary."
    assert entry["support"][0]["units"] == [COUNTS]
    assert run(capsys, "check")[0] == 0


def test_retarget_needs_a_stale_entry(env, capsys):
    with pytest.raises(SystemExit) as err:
        run(capsys, "retarget", "popcnt", "abc", "1")
    assert "matches 0 stale entries" in str(err.value)


def test_prune_drops_only_stale_entries(env, capsys):
    cite_summary(capsys)
    run(capsys, "mark", "popcnt", "3", "--as", "editorial", "--note", "n")
    page = env / "instructions" / "popcnt.md"
    page.write_text(page.read_text().replace("Summary of POPCNT.", "Another summary."))
    assert run(capsys, "check")[0] == 1
    code, out, _ = run(capsys, "prune")
    assert code == 0 and "popcnt: dropped 1 stale entry" in out
    assert [e["how"] for e in ledger(env)["claims"]] == ["editorial"]
    assert run(capsys, "check")[0] == 0
    assert "nothing stale" in run(capsys, "prune")[1]


def test_check_no_sources_does_not_need_the_files_run_evidence_names(env, capsys):
    run(capsys, "mark", "popcnt", "1", "--as", "run", "--ref", "tests/asm/missing.asm")
    code, _, err = run(capsys, "check")
    assert code == 1 and "tests/asm/missing.asm" in err
    code, out, _ = run(capsys, "check", "--no-sources")
    assert code == 0 and out.startswith("OK:")
