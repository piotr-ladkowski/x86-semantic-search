"""`docx86 eval`: rank bars per query, negatives against the floor, exit status."""

import argparse

import yaml

from docx86 import cli
from docx86.main import build_engine


def run_eval(settings, capsys, spec: dict) -> tuple[int, str]:
    (settings.content_dir / "eval.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    code = cli.cmd_eval(argparse.Namespace(), settings)
    return code, capsys.readouterr().out


def test_eval_passes_when_ranks_and_negatives_hold(settings, capsys):
    build_engine(settings)  # writes the index the command loads
    s = settings.model_copy(update={"search_floor": 0.5})
    code, out = run_eval(
        s,
        capsys,
        {
            "queries": [
                {"query": "count the number of set bits", "expect": "popcnt", "top": 1},
                {"query": "register behaviour", "kind": "article", "expect": "regs"},
            ],
            "negatives": ["zebra giraffe"],
        },
    )
    assert code == 0, out
    assert "hit@1 2/2" in out and "negatives rejected 1/1" in out
    assert "rank=1/1" in out and "rank=1/3" in out and "lead=+" in out
    assert "floor 0.50: weakest expected page 1.000, strongest negative 0.000" in out


def test_eval_fails_on_a_miss_or_a_leak(settings, capsys):
    build_engine(settings)
    s = settings.model_copy(update={"search_floor": 0.5})
    code, out = run_eval(
        s,
        capsys,
        {
            "queries": [{"query": "pointer arithmetic", "expect": "popcnt", "top": 1}],
            "negatives": ["count the number of set bits"],  # a verbatim phrase: scores 1.0
        },
    )
    assert code == 1
    assert "MISS" in out and "LEAK" in out and "misses 1" in out


def test_eval_warns_when_the_expected_page_is_weak(settings, capsys):
    build_engine(settings)
    s = settings.model_copy(update={"search_floor": 0.99})
    code, out = run_eval(s, capsys, {"queries": [{"query": "count set bits", "expect": "popcnt"}]})
    assert code == 0 and "warning: expected page is marked weak: popcnt" in out
