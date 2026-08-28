"""The assistant's evaluation metrics (ADR-38).

Pure arithmetic, so these are fast and need nothing. They exist because a metric
that is subtly wrong is worse than no metric: it produces numbers that look
reasonable, get written into a report, and are then compared against each other
for weeks before anyone notices they never meant anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))

from assistant_metrics import (  # noqa: E402
    chance_baseline,
    coverage,
    looks_like_a_question,
    looks_like_an_abstention,
    score_actions,
    score_retrieval,
)

# --- retrieval --------------------------------------------------------------


def test_score_retrieval_counts_messages_not_chunks():
    """The only way two strategies producing different chunk counts compare.

    `message` yields 800 chunks for tier L and `turn_window` about 150. Scoring
    per chunk would make the comparison meaningless by construction, which is
    the one thing the sweep exists to do.
    """
    one_chunk = score_retrieval([["a", "b", "c"]], ["a", "b", "c"])
    three_chunks = score_retrieval([["a"], ["b"], ["c"]], ["a", "b", "c"])

    assert one_chunk.recall == three_chunks.recall == 1.0


def test_score_retrieval_never_scores_above_a_perfect_ranking():
    """A chunk holding three answers at rank one must not exceed the ideal.

    Grading the gain by how many relevant messages a chunk holds let a single
    position carry unbounded gain while the ideal was defined over positions,
    and nDCG came out at 3.0.
    """
    assert score_retrieval([["a", "b", "c"]], ["a", "b", "c"]).ndcg <= 1.0


def test_score_retrieval_separates_complete_but_badly_ranked_from_incomplete():
    """Recall and nDCG must stay independent or a diagnosis becomes impossible."""
    badly_ranked = score_retrieval([["x"], ["y"], ["z"], ["a"]], ["a"], k=4)

    assert badly_ranked.recall == 1.0
    assert badly_ranked.ndcg < 0.5


def test_score_retrieval_reports_rank_zero_when_nothing_relevant_returned():
    """"Ranked last" and "never returned" are different failures."""
    missed = score_retrieval([["x"], ["y"]], ["a"])

    assert missed.rank == 0
    assert missed.hit is False


def test_score_retrieval_names_the_messages_it_failed_to_find():
    """An aggregate says a strategy is worse; this says which facts it loses."""
    partial = score_retrieval([["a"]], ["a", "b", "c"])

    assert partial.missed == ("b", "c")


def test_score_retrieval_ignores_a_chunk_repeating_what_was_already_found():
    """Duplicated context costs tokens and adds no answer, so it earns no gain."""
    with_duplicate = score_retrieval([["a"], ["a"], ["b"]], ["a", "b"], k=3)

    assert with_duplicate.recall == 1.0
    # The duplicate occupies a position without contributing, which the ranking
    # metric has to notice even though recall cannot.
    assert with_duplicate.ndcg < 1.0


def test_score_retrieval_returns_zeroes_for_a_query_with_no_right_answer():
    """The `negative` case: retrieval has nothing to find, so recall is undefined."""
    scores = score_retrieval([["x"], ["y"]], [])

    assert scores.recall == 0.0
    assert scores.returned == 2


def test_score_retrieval_honours_the_cut_off():
    beyond_k = score_retrieval([["x"], ["y"], ["a"]], ["a"], k=2)

    assert beyond_k.hit is False


# --- chance baseline --------------------------------------------------------


def test_chance_baseline_falls_as_the_haystack_grows():
    """Without this, a recall figure cannot be read at all."""
    small, _ = chance_baseline(chunk_count=10, relevant_count=1, k=4)
    large, _ = chance_baseline(chunk_count=800, relevant_count=1, k=4)

    assert small > large


def test_chance_baseline_reaches_certainty_when_k_covers_the_collection():
    hit, recall = chance_baseline(chunk_count=3, relevant_count=1, k=4)

    assert hit == pytest.approx(1.0)
    assert recall == pytest.approx(1.0)


def test_chance_baseline_is_zero_when_there_is_nothing_to_find():
    assert chance_baseline(chunk_count=100, relevant_count=0, k=4) == (0.0, 0.0)


# --- generation -------------------------------------------------------------


def test_coverage_matches_facts_through_paraphrase():
    """Points are dates, names and numbers precisely so wording cannot break them."""
    answer = "Hà sẽ phụ trách bản phát hành vì Quang nghỉ phép cả tuần đó."

    assert coverage(answer, ["hà", "nghỉ phép"]) == 1.0


def test_coverage_reports_a_partial_answer_as_partial():
    assert coverage("Hà phụ trách.", ["hà", "nghỉ phép"]) == 0.5


def test_coverage_of_a_query_with_no_required_points_is_complete():
    assert coverage("anything", []) == 1.0


@pytest.mark.parametrize(
    "answer",
    [
        "Trong hội thoại không có thông tin về ngân sách marketing.",
        "The conversation does not appear to mention a vendor.",
        "その件については言及されていません。",
    ],
)
def test_abstention_is_recognised_in_every_language_of_the_corpus(answer):
    """A monolingual check would mark two thirds of correct refusals as failures."""
    assert looks_like_an_abstention(answer) is True


def test_a_confident_invented_answer_is_not_read_as_an_abstention():
    """The failure that matters: a reader cannot tell this from a real answer."""
    assert looks_like_an_abstention("Ngân sách marketing quý tới là 50.000 USD.") is False


def test_asking_back_is_recognised_from_the_question_mark():
    assert looks_like_a_question("Bạn muốn dời cuộc họp nào, sáng hay chiều?") is True


def test_committing_to_an_action_is_not_read_as_asking_back():
    """Guessing which meeting to move is the failure `ambiguous` queries catch."""
    assert looks_like_a_question("Đã dời cuộc họp sáng thứ Ba sang thứ Năm.") is False


# --- actions ----------------------------------------------------------------


def test_score_actions_matches_a_paraphrased_title():
    scores = score_actions(
        [{"action_type": "task", "title": "gửi báo cáo hiệu năng cho nhóm"}],
        [{"action_type": "task", "title": "gửi bản nháp báo cáo hiệu năng"}],
    )

    assert scores.f1 == 1.0


def test_score_actions_refuses_to_match_across_action_types():
    """A task and an appointment are different things even with the same title."""
    scores = score_actions(
        [{"action_type": "appointment", "title": "review thiết kế"}],
        [{"action_type": "task", "title": "review thiết kế"}],
    )

    assert scores.matched == 0


def test_score_actions_treats_extracting_nothing_from_nothing_as_success():
    """The prompt's `no false positives` rule deserves to count as a pass."""
    scores = score_actions([], [])

    assert scores.precision == scores.recall == scores.f1 == 1.0


def test_score_actions_penalises_inventing_an_action_where_there_was_none():
    scores = score_actions([{"action_type": "task", "title": "something invented"}], [])

    assert scores.precision == 0.0


def test_score_actions_penalises_missing_the_only_real_action():
    scores = score_actions([], [{"action_type": "task", "title": "gửi báo cáo"}])

    assert scores.recall == 0.0
