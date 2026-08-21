"""Aggregation helpers shared by the evaluation harness and the metrics report.

Two kinds of number live here. `percentile` and `group_scores` summarise a list
of scored samples and were written for `eval/run_eval.py`; they moved here so the
metrics report and the stats endpoint can use the same definitions rather than a
second implementation that drifts. `summarize_attempts` reads the
`translation_attempts` table and answers the questions the log exists for: what
share of translations fell back, which model actually served them, and how long
each language pair takes.

Nothing here writes. Nothing here raises on empty input — a report over a fresh
database prints zeroes rather than failing.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import TranslationAttempt

# Outcomes where the reader did not get the configured LLM's translation. Both
# are failures of the primary path, and both are invisible in
# `translation_results` alone, which is why the fallback rate is computed here.
FALLBACK_OUTCOMES = frozenset({"secondary", "original"})


def percentile(values: list[int], pct: float) -> float:
    """Percentile of a sequence, safe on empty and single-element input.

    ``statistics.quantiles`` needs at least two points; below that the only
    reasonable estimate is the single value itself.
    """
    if not values:
        return 0.0
    if len(values) < 2:
        return float(values[0])

    ordered = sorted(values)
    rank = pct / 100 * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def group_scores(
    scored: list[dict],
    key: str,
    pass_threshold: float,
) -> dict[str, tuple[int, float, int]]:
    """Group scored samples by one field: {value: (count, mean score, passed)}.

    Used for the per-dimension breakdowns (category, chat type, context level,
    language pair) so the report can show where the agent actually degrades
    rather than only a single aggregate number.

    The count is returned alongside the mean because several breakdowns have
    buckets of one or two samples, where a mean on its own invites more
    confidence than the sample size supports.
    """
    buckets: dict[str, list[float]] = {}
    for record in scored:
        buckets.setdefault(record.get(key) or "(unknown)", []).append(record["score"])

    return {
        value: (
            len(scores),
            statistics.mean(scores),
            sum(1 for score in scores if score >= pass_threshold),
        )
        for value, scores in sorted(buckets.items())
    }


@dataclass(frozen=True, slots=True)
class LanguagePairStats:
    """How many translations a language pair carried, and how long they took."""

    count: int
    p50_ms: float
    p95_ms: float


@dataclass(frozen=True, slots=True)
class AttemptSummary:
    """Everything the metrics report and the stats endpoint show.

    Counters are plain dicts so the whole object serialises to JSON without a
    custom encoder.
    """

    total: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)
    fallback_rate: float = 0.0
    detect_methods: dict[str, int] = field(default_factory=dict)
    fallback_reasons: dict[str, int] = field(default_factory=dict)
    models_served: dict[str, int] = field(default_factory=dict)
    language_pairs: dict[str, LanguagePairStats] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    total_ms_p50: float = 0.0
    total_ms_p95: float = 0.0


async def summarize_attempts(
    session: AsyncSession,
    *,
    since: datetime | None = None,
) -> AttemptSummary:
    """Aggregate the attempt log into the figures the report displays.

    Rows are fetched and aggregated in Python rather than in SQL. Percentiles
    have no portable SQL form — SQLite has no `percentile_cont` — and computing
    part of the summary in the database and the rest here would mean two
    definitions of the same metric. The volume this project produces (one row
    per recipient bucket per message — a bucket being a language and a standing,
    so up to four per language) stays well inside what a single query can
    return; `since` is there for when it does not.

    `language_pairs` stays keyed by the language pair alone, deliberately.
    NFR-01 is about the delay a reader experiences, and that is the same
    question whichever standing they were translated at; splitting the key would
    turn one headline latency figure into four thinner samples. The consequence
    to keep in mind when reading it: `count` counts buckets, not messages.

    Args:
        session: An open database session.
        since: Only count attempts created at or after this moment. None counts
            everything ever recorded.

    Returns:
        A summary with zeroes throughout when no attempt matches.
    """
    query = select(
        TranslationAttempt.outcome,
        TranslationAttempt.detect_method,
        TranslationAttempt.fallback_reason,
        TranslationAttempt.model_served,
        TranslationAttempt.source_language_declared,
        TranslationAttempt.source_language_detected,
        TranslationAttempt.target_language,
        TranslationAttempt.input_tokens,
        TranslationAttempt.output_tokens,
        TranslationAttempt.total_ms,
    )
    if since is not None:
        query = query.where(TranslationAttempt.created_at >= since)

    rows = (await session.execute(query)).all()
    if not rows:
        return AttemptSummary()

    outcomes: Counter[str] = Counter()
    detect_methods: Counter[str] = Counter()
    fallback_reasons: Counter[str] = Counter()
    models_served: Counter[str] = Counter()
    durations_by_pair: dict[str, list[int]] = {}
    all_durations: list[int] = []
    input_tokens = 0
    output_tokens = 0

    for row in rows:
        outcomes[row.outcome] += 1
        detect_methods[row.detect_method or "(none)"] += 1
        if row.fallback_reason:
            fallback_reasons[row.fallback_reason] += 1
        models_served[row.model_served or "(none)"] += 1
        input_tokens += row.input_tokens
        output_tokens += row.output_tokens

        # The detected language is the one the translation was actually
        # performed from; the declared one is a guess from the sender's profile
        # and is wrong exactly when detection was worth running.
        source = row.source_language_detected or row.source_language_declared
        pair = f"{source}->{row.target_language}"
        durations_by_pair.setdefault(pair, []).append(row.total_ms)
        all_durations.append(row.total_ms)

    fallback_count = sum(outcomes[outcome] for outcome in FALLBACK_OUTCOMES)

    return AttemptSummary(
        total=len(rows),
        outcomes=dict(outcomes.most_common()),
        fallback_rate=fallback_count / len(rows),
        detect_methods=dict(detect_methods.most_common()),
        fallback_reasons=dict(fallback_reasons.most_common()),
        models_served=dict(models_served.most_common()),
        language_pairs={
            pair: LanguagePairStats(
                count=len(durations),
                p50_ms=percentile(durations, 50),
                p95_ms=percentile(durations, 95),
            )
            for pair, durations in sorted(durations_by_pair.items())
        },
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_ms_p50=percentile(all_durations, 50),
        total_ms_p95=percentile(all_durations, 95),
    )
