"""Structural checks on the golden set.

Cheap guards against the ways a hand-maintained JSONL file goes wrong: a
duplicated id silently overwrites a scenario, a missing field crashes a run
forty samples in, and a language the system does not support is scored against
a translation the agent was never asked to produce.

Fixtures live in this file rather than tests/conftest.py, which is shared
across all feature areas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.auth import SUPPORTED_LANGUAGES

GOLDEN_SET = Path(__file__).resolve().parents[2] / "eval" / "golden_set.jsonl"

# The languages the golden set was built to cover. A subset of
# SUPPORTED_LANGUAGES: the product accepts thirteen codes, and the evaluation
# makes no claim about the five it never exercises.
EVALUATED_LANGUAGES = {"vi", "en", "zh", "fr", "es", "ja", "de", "th"}

REQUIRED_KEYS = {
    "id",
    "category",
    "chat_type",
    "context_level",
    "source_language",
    "target_language",
    "context_messages",
    "original_text",
    "expected_translation",
    "note",
}


@pytest.fixture(scope="module")
def samples() -> list[dict]:
    """Every row of the golden set, parsed."""
    with GOLDEN_SET.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_every_row_has_the_same_keys(samples):
    """A missing field would fail a run partway through, after paying for it."""
    for sample in samples:
        assert set(sample) == REQUIRED_KEYS, sample.get("id")


def test_ids_are_unique(samples):
    """Ids identify samples across runs, so a duplicate hides one of them."""
    ids = [sample["id"] for sample in samples]

    assert len(ids) == len(set(ids))


def test_languages_are_ones_the_system_supports(samples):
    """Scoring a pair the product cannot offer measures nothing useful."""
    for sample in samples:
        assert sample["source_language"] in SUPPORTED_LANGUAGES, sample["id"]
        assert sample["target_language"] in SUPPORTED_LANGUAGES, sample["id"]


def test_classification_fields_use_known_values(samples):
    """The report groups by these, and a typo would create a bucket of one."""
    for sample in samples:
        assert sample["chat_type"] in {"direct", "group"}, sample["id"]
        assert sample["context_level"] in {"rich", "poor"}, sample["id"]


def test_both_chat_types_and_both_context_levels_are_represented(samples):
    """The report breaks results down by these, so an empty bucket is a hole.

    Group threads and bilingual threads exercise different behaviour, as do
    rich and poor context; a set that lost one of them would still produce a
    report, just one that quietly stopped measuring something.
    """
    assert {s["chat_type"] for s in samples} == {"direct", "group"}
    assert {s["context_level"] for s in samples} == {"rich", "poor"}


def test_the_set_covers_the_languages_it_was_built_for(samples):
    """Coverage is the point of the set: a language absent here is untested.

    These eight are the scope the set was written to, not the full thirteen
    `SUPPORTED_LANGUAGES` allows — the product accepts more codes than the
    evaluation makes any claim about, and this test records which.
    """
    covered = {s["source_language"] for s in samples} | {
        s["target_language"] for s in samples
    }

    assert EVALUATED_LANGUAGES <= covered
