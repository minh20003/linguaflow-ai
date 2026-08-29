"""Metrics for the Assistant Agent, computed without a model.

Separate from `eval/quality_metrics.py`, which scores translations against a
reference sentence. Nothing there transfers: an assistant is graded on whether it
*found* the right messages and whether what it wrote is *traceable to them*, and
neither question has a reference string to compare against.

Retrieval is scored **per message, not per chunk**. A chunk is an artefact of one
chunking strategy — `message` produces 800 of them for the L tier and
`turn_window` produces about 150 — so counting chunks would make the strategies
incomparable by construction, which is the one thing the sweep exists to do.
Every strategy is therefore asked the same question: of the messages that carry
the answer, how many did the returned chunks actually contain?

Every retrieval figure is reported beside a **chance baseline**. Without one, a
hit rate is unreadable: `sweep-20260822-064517` measured 22% and the number only
became meaningful next to the 8.8% a random retriever scores on the same corpus.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RetrievalScores:
    """How well one query's retrieval did.

    `rank` is 1-based and 0 when nothing relevant came back, which separates
    "ranked last" from "not returned at all" — two very different failures that a
    hit rate alone reports identically. The same distinction `quality_metrics.RetrievalScores`
    draws for the translation path.
    """

    hit: bool = False
    recall: float = 0.0
    precision: float = 0.0
    ndcg: float = 0.0
    reciprocal_rank: float = 0.0
    rank: int = 0
    returned: int = 0
    # Messages the answer needed that no returned chunk contained. Kept because
    # an aggregate recall says a strategy is worse and this says which facts it
    # loses, which is the difference between a number and a diagnosis.
    missed: tuple[str, ...] = field(default_factory=tuple)


def score_retrieval(
    retrieved: Sequence[Sequence[str]],
    relevant: Sequence[str],
    *,
    k: int | None = None,
) -> RetrievalScores:
    """Score one query's retrieval, counting messages rather than chunks.

    Args:
        retrieved: For each returned chunk in rank order, the ids of the messages
            it covers. Chunks, not messages, because that is what retrieval
            returns and because one chunk covering three relevant messages is a
            better result than three chunks covering one each.
        relevant: Ids of the messages that carry the answer.
        k: Cut-off. ``None`` scores everything returned.

    Returns:
        Zeroed scores when ``relevant`` is empty. That is the `negative` case,
        where retrieval has nothing to find and the real measurement is whether
        generation refuses — see `abstain_rate`.
    """
    cut = list(retrieved[:k] if k is not None else retrieved)
    wanted = set(relevant)
    if not wanted:
        return RetrievalScores(returned=len(cut))

    found: set[str] = set()
    first_hit = 0
    # Gain is binary — did this chunk bring anything new — rather than graded on
    # how many relevant messages it holds. Grading by count would let one chunk
    # covering three answers score above the ideal, since the ideal is defined
    # over positions and a single position can then carry unbounded gain.
    # Completeness is not lost by this: `recall` reports it directly, and the two
    # numbers stay independent, which is what makes a low nDCG with high recall
    # readable as "found it all, ranked it badly".
    gains: list[int] = []
    useful = 0

    for position, chunk in enumerate(cut, start=1):
        fresh = (set(chunk) & wanted) - found
        if set(chunk) & wanted:
            useful += 1
            if not first_hit:
                first_hit = position
        gains.append(1 if fresh else 0)
        found |= fresh

    dcg = sum(gain / math.log2(index + 1) for index, gain in enumerate(gains, start=1))
    # The ideal ranking puts a new relevant message at every position from the
    # top, for as many positions as there are relevant messages to place — or as
    # many as were returned, whichever is fewer.
    ideal = sum(
        1 / math.log2(index + 1) for index in range(1, min(len(wanted), len(cut) or 1) + 1)
    )

    return RetrievalScores(
        hit=bool(found),
        recall=len(found) / len(wanted),
        precision=useful / len(cut) if cut else 0.0,
        ndcg=dcg / ideal if ideal else 0.0,
        reciprocal_rank=1 / first_hit if first_hit else 0.0,
        rank=first_hit,
        returned=len(cut),
        missed=tuple(sorted(wanted - found)),
    )


def chance_baseline(
    *, chunk_count: int, relevant_count: int, k: int
) -> tuple[float, float]:
    """What a retriever picking chunks at random would score.

    Reported beside every real figure, because a recall number alone cannot be
    read. Over 34 candidates at k=3 a random retriever already scores 8.8% hit
    rate — a strategy measuring 22% is doing something, but far less than the
    number suggests on its own.

    Args:
        chunk_count: How many chunks the strategy produced for this conversation.
        relevant_count: How many messages carry the answer.
        k: Cut-off.

    Returns:
        ``(hit_rate, recall)`` expected from a uniform random ranking.
    """
    if chunk_count <= 0 or relevant_count <= 0 or k <= 0:
        return 0.0, 0.0

    draws = min(k, chunk_count)
    # Probability that one particular relevant chunk is missed by all `draws`
    # picks, under sampling without replacement.
    miss = 1.0
    for step in range(draws):
        remaining = chunk_count - step
        if remaining <= 0:
            break
        miss *= max(0.0, (remaining - 1) / remaining)

    per_item_recall = 1.0 - miss
    # At least one of `relevant_count` independent-ish items found.
    hit = 1.0 - (miss**relevant_count)
    return hit, per_item_recall


# --- Generation ------------------------------------------------------------


def coverage(answer: str, points: Sequence[str]) -> float:
    """Share of the required facts that appear in the answer.

    Substring matching, case-folded. Crude on purpose: the alternative is a model
    judging whether a point was "expressed", which puts the thing being measured
    inside the measurement. The points in `corpus_spec` are chosen to survive
    paraphrase — a date, a name, a number — so a correct answer contains them
    however it is worded.
    """
    if not points:
        return 1.0
    lowered = (answer or "").casefold()
    return sum(1 for point in points if point.casefold() in lowered) / len(points)


# Words a refusal is built from, in the three languages of this corpus. Matching
# a phrase rather than classifying with a model, for the reason above: a judge
# deciding "was this a refusal" is one more model to be wrong.
_ABSTAIN_MARKERS = (
    "không có thông tin",
    "không tìm thấy",
    "không đề cập",
    "chưa được nhắc",
    "no information",
    "not mentioned",
    "could not find",
    "does not appear",
    "情報がありません",
    "見つかりません",
    "言及されていません",
)


def looks_like_an_abstention(answer: str) -> bool:
    """Whether the answer declines to answer.

    The correct behaviour for a `negative` query, and the one systems that score
    well everywhere else routinely fail. It matters more than it looks: a
    confident invented answer is worse than no answer, because the reader has no
    way to tell it apart from a real one.
    """
    lowered = (answer or "").casefold()
    return any(marker.casefold() in lowered for marker in _ABSTAIN_MARKERS)


def looks_like_a_question(answer: str) -> bool:
    """Whether the assistant asked something back.

    The correct behaviour for an `ambiguous` query. Checked structurally rather
    than semantically: a reply containing a question mark and no committed action
    is asking; one that picked a meeting and scheduled it is guessing.
    """
    return "?" in (answer or "") or "？" in (answer or "")


@dataclass(frozen=True, slots=True)
class ActionScores:
    """Precision, recall and F1 over the actions extracted from a conversation."""

    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    owner_accuracy: float = 0.0
    time_accuracy: float = 0.0
    matched: int = 0
    expected: int = 0
    produced: int = 0


def score_actions(
    produced: Sequence[dict], expected: Sequence[dict]
) -> ActionScores:
    """Compare extracted actions against the ones the corpus planted.

    Matched on title overlap rather than on equality: the title is generated
    text, and demanding an exact string would score paraphrase as a miss while
    saying nothing about whether the action is right. Type must match exactly,
    because a task and an appointment are different things to a user even when
    they share a title.

    `expected` empty and `produced` empty scores 1.0 across the board — correctly
    extracting nothing from small talk is the `no false positives` requirement in
    the extraction prompt, and it deserves to count as a success rather than as
    an undefined division.
    """
    if not expected and not produced:
        return ActionScores(precision=1.0, recall=1.0, f1=1.0, owner_accuracy=1.0, time_accuracy=1.0)
    if not expected:
        return ActionScores(produced=len(produced))
    if not produced:
        return ActionScores(expected=len(expected))

    unmatched = list(expected)
    matched: list[tuple[dict, dict]] = []
    for candidate in produced:
        for target in unmatched:
            if candidate.get("action_type") != target.get("action_type"):
                continue
            if _titles_overlap(candidate.get("title", ""), target.get("title", "")):
                matched.append((candidate, target))
                unmatched.remove(target)
                break

    precision = len(matched) / len(produced)
    recall = len(matched) / len(expected)
    f1 = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
    owner_hits = sum(
        1 for candidate, target in matched
        if not target.get("owner") or candidate.get("owner") == target.get("owner")
    )
    time_hits = sum(
        1 for candidate, target in matched
        if not target.get("when")
        or target["when"].casefold() in str(candidate.get("when", "")).casefold()
    )

    return ActionScores(
        precision=precision,
        recall=recall,
        f1=f1,
        owner_accuracy=owner_hits / len(matched) if matched else 0.0,
        time_accuracy=time_hits / len(matched) if matched else 0.0,
        matched=len(matched),
        expected=len(expected),
        produced=len(produced),
    )


def _titles_overlap(left: str, right: str, *, threshold: float = 0.4) -> bool:
    """Whether two action titles describe the same thing.

    Word overlap against the shorter title, so "gửi bản nháp báo cáo hiệu năng"
    matches "gửi báo cáo hiệu năng cho nhóm". The threshold is deliberately
    forgiving: a false match inflates precision by one action, while demanding
    exact text would report a working extractor as broken.
    """
    left_words = {word for word in left.casefold().split() if len(word) > 2}
    right_words = {word for word in right.casefold().split() if len(word) > 2}
    if not left_words or not right_words:
        return False
    return len(left_words & right_words) / min(len(left_words), len(right_words)) >= threshold


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean, zero for an empty sequence."""
    return sum(values) / len(values) if values else 0.0
