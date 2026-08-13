"""Tests for how the evaluation harness turns judge replies into numbers.

`eval/` is a script directory, not a package, so the module is loaded by path.

Fixtures live in this file rather than tests/conftest.py, which is shared
across all feature areas.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

EVAL_PATH = Path(__file__).resolve().parents[2] / "eval" / "run_eval.py"


def load_run_eval():
    """Import eval/run_eval.py under its own name, once per session."""
    if "run_eval" in sys.modules:
        return sys.modules["run_eval"]

    spec = importlib.util.spec_from_file_location("run_eval", EVAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_eval"] = module
    spec.loader.exec_module(module)
    return module


run_eval = load_run_eval()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.85", 0.85),
        ("1.0", 1.0),
        ("0", 0.0),
        ("  0.9\n", 0.9),
    ],
)
def test_a_bare_number_is_read_as_the_score(raw, expected):
    """The format the prompt asks for, with whitespace the model may add."""
    assert run_eval.parse_score(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "8/10",  # the loose pattern read this as 1.0
        "Score: 0.9",
        "0.9 — the pronoun choice is correct",
        "high",
        "",
    ],
)
def test_a_reply_that_is_not_a_bare_number_is_refused(raw):
    """A judge that ignored the output format also ignored its constraints.

    "8/10" is the case that matters. The previous pattern searched anywhere in
    the reply, found the "1" inside "10", and read a mediocre translation as a
    perfect 1.0.
    """
    assert run_eval.parse_score(raw) is None


def test_passthrough_samples_are_kept_out_of_the_score():
    """A sample returned verbatim scores ~1.0 without a model being called.

    Left in, it raises the average by rewarding work that never happened.
    """
    results = [
        {
            "outcome": "passthrough",
            "score": 1.0,
            "category": "same-language",
            "chat_type": "direct",
            "context_level": "poor",
            "language_pair": "vi->vi",
            "latency_ms": 0,
            "is_fallback": False,
        },
        {
            "outcome": "llm",
            "score": 0.6,
            "category": "pronoun",
            "chat_type": "direct",
            "context_level": "rich",
            "language_pair": "vi->en",
            "latency_ms": 800,
            "is_fallback": False,
        },
    ]

    summary = run_eval.summarize(results)

    assert summary["total"] == 2
    assert summary["passthrough"] == 1
    assert summary["translated"] == 1
    assert summary["avg_score"] == 0.6
    assert "vi->vi" not in summary["by_language_pair"]


def test_categories_carry_their_sample_count():
    """Most category buckets hold one or two samples; a bare mean hides that."""
    results = [
        {
            "outcome": "llm",
            "score": score,
            "category": "idiom",
            "chat_type": "group",
            "context_level": "rich",
            "language_pair": "vi->en",
            "latency_ms": 500,
            "is_fallback": False,
        }
        for score in (1.0, 0.5)
    ]

    assert run_eval.summarize(results)["by_category"]["idiom"] == (2, 0.75, 1)


def test_an_unscored_sample_still_counts_towards_fallbacks():
    """The two figures have different denominators, and the report says so."""
    results = [
        {
            "outcome": "original",
            "score": None,
            "category": "refusal",
            "chat_type": "direct",
            "context_level": "poor",
            "language_pair": "vi->en",
            "latency_ms": 300,
            "is_fallback": True,
        }
    ]

    summary = run_eval.summarize(results)

    assert summary["scored"] == 0
    assert summary["fallback"] == 1
    assert summary["avg_score"] == 0.0
