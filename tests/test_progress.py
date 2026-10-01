from docx86.content import load_content
from docx86.progress import compute, render_summary, sync


def test_counts_follow_roster(content_dir):
    p = compute(load_content(content_dir))
    assert (p.total, p.documented) == (4, 3)  # roster has `rol` without a page
    assert p.count("todo") == 1 and p.count("draft") == 3 and p.count("reviewed") == 0
    assert "3 / 4 (75%)" in render_summary(p)


def test_sync_writes_then_reports_clean(tmp_path, content_dir):
    root = tmp_path / "repo"
    (root / "content").mkdir(parents=True)
    (root / "README.md").write_text(
        "# x\n<!-- progress:start -->\nold\n<!-- progress:end -->\ntail\n"
    )
    content = load_content(content_dir)

    assert len(sync(content, root, write=False)) == 2  # check mode: both stale, nothing written
    assert "old" in (root / "README.md").read_text()

    sync(content, root, write=True)
    text = (root / "README.md").read_text()
    assert "3 / 4" in text and text.startswith("# x\n") and text.endswith("\ntail\n")
    assert (
        "- [x] [`LEA`](instructions/lea.md) — draft" in (root / "content" / "README.md").read_text()
    )
    assert "- [ ] `ROL` (`rol`) — todo" in (root / "content" / "README.md").read_text()
    assert sync(content, root, write=False) == []  # idempotent
