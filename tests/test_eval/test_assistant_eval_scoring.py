"""Scoring and aggregation in the assistant's end-to-end harness (ADR-40).

The graph itself is exercised elsewhere; what is under test here is the part
that turns one reply into a number, and the part that turns a pile of numbers
into a verdict. Both are places a subtle mistake produces a plausible figure
that is measuring something else — the worst kind of bug in a measurement.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))

from build_assistant_corpus import CorpusQuery  # noqa: E402
from run_assistant_eval import score_one, summarize  # noqa: E402


def _query(kind: str, **overrides) -> CorpusQuery:
    return CorpusQuery(
        key=overrides.get("key", "k"),
        kind=kind,
        question=overrides.get("question", "câu hỏi"),
        relevant_indexes=overrides.get("relevant_indexes", []),
        answer_points=overrides.get("answer_points", []),
    )


# --- scoring one answer -----------------------------------------------------


def test_a_grounded_answer_is_scored_on_the_facts_it_contains():
    row = score_one(
        _query("single_hop", answer_points=["13"]),
        "Deadline milestone thanh toán là ngày 13 tháng 9.",
    )

    assert row["coverage"] == 1.0


def test_a_negative_question_is_scored_only_on_whether_it_declined():
    """It has no points to cover; a coverage of 0.0 would enter the wrong average."""
    row = score_one(
        _query("negative"), "Trong hội thoại không có thông tin về ngân sách."
    )

    assert row["abstained"] is True
    assert "coverage" not in row


def test_a_confident_invention_fails_the_negative_question():
    """The failure users notice: indistinguishable from a real answer."""
    row = score_one(_query("negative"), "Ngân sách marketing quý tới là 50.000 USD.")

    assert row["abstained"] is False


def test_an_ambiguous_question_is_scored_only_on_whether_it_asked_back():
    row = score_one(_query("ambiguous"), "Bạn muốn dời cuộc họp sáng hay chiều?")

    assert row["asked_back"] is True
    assert "coverage" not in row


def test_guessing_which_meeting_to_move_fails_the_ambiguous_question():
    row = score_one(_query("ambiguous"), "Đã dời cuộc họp sáng thứ Ba sang thứ Năm.")

    assert row["asked_back"] is False


def test_declining_a_question_the_conversation_does_answer_is_recorded():
    """Otherwise a run that abstains its way to a clean faithfulness score hides it."""
    row = score_one(
        _query("single_hop", answer_points=["13"]),
        "Mình không tìm thấy thông tin về deadline trong hội thoại.",
    )

    assert row["coverage"] == 0.0
    assert row["abstained"] is True


# --- aggregation ------------------------------------------------------------


def _row(kind: str, **fields) -> dict:
    base = {"key": "k", "kind": kind, "latency_ms": 100, "replans": 1}
    return {**base, **fields}


def test_the_kinds_are_averaged_separately_because_they_measure_different_things():
    """One average over all of them would describe none of them."""
    summary = summarize(
        [
            _row("single_hop", coverage=1.0, abstained=False),
            _row("negative", abstained=True),
            _row("ambiguous", asked_back=True),
        ]
    )

    assert summary["coverage"] == 1.0
    assert summary["abstain_accuracy"] == 1.0
    assert summary["clarify_accuracy"] == 1.0


def test_coverage_is_reported_per_kind_as_well_as_overall():
    """An overall figure hides which kind of question the system cannot answer."""
    summary = summarize(
        [
            _row("single_hop", coverage=1.0, abstained=False),
            _row("multi_hop", coverage=0.0, abstained=False),
        ]
    )

    assert summary["coverage_by_kind"] == {"single_hop": 1.0, "multi_hop": 0.0}


def test_an_assistant_that_declines_everything_is_visible_as_such():
    """A perfect abstain rate is easy to reach by never answering anything.

    `false_abstain_rate` is the other half a single rate hides — and without it
    the safest-looking run is the one that helps nobody.
    """
    summary = summarize(
        [
            _row("negative", abstained=True),
            _row("single_hop", coverage=0.0, abstained=True),
            _row("multi_hop", coverage=0.0, abstained=True),
        ]
    )

    assert summary["abstain_accuracy"] == 1.0
    assert summary["false_abstain_rate"] == 1.0


def test_a_run_with_no_negative_questions_reports_no_abstain_rate():
    """None rather than zero: nothing measured it, which is not the same as failing."""
    summary = summarize([_row("single_hop", coverage=1.0, abstained=False)])

    assert summary["abstain_accuracy"] is None


def test_a_judge_that_could_not_score_is_left_out_of_the_average():
    """A timed-out judge has not observed an unfaithful answer.

    Scoring it as zero would move the average in a direction nothing measured.
    """
    summary = summarize(
        [
            _row("single_hop", coverage=1.0, abstained=False, faithfulness=1.0),
            _row("multi_hop", coverage=1.0, abstained=False, faithfulness=None),
        ]
    )

    assert summary["faithfulness"] == 1.0
    assert summary["judged"] == 1


def test_the_replan_average_is_reported_so_the_ceiling_can_be_judged():
    summary = summarize(
        [
            _row("single_hop", coverage=1.0, abstained=False, replans=1),
            _row("multi_hop", coverage=1.0, abstained=False, replans=3),
        ]
    )

    assert summary["avg_replans"] == 2.0
