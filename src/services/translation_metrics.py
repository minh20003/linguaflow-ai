"""Low-cardinality in-process metrics for the translation pipeline."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class TranslationMetrics:
    """Collect counters, duration summaries, and gauges without request labels.

    Export adapters can read :meth:`snapshot` later. Keeping this collector
    dependency-free preserves the current deployment while preventing accidental
    high-cardinality labels such as ``message_id`` or ``user_id``.
    """

    _COUNTERS = (
        "translation_jobs_total",
        "translation_completed_total",
        "translation_failed_total",
        "translation_fallback_total",
        "language_detection_llm_total",
        "outbox_retry_total",
        "translation_stale_total",
    )
    _DURATIONS = ("translation_duration_seconds", "translation_first_token_seconds")
    _GAUGES = ("translation_queue_depth", "translation_active_jobs", "outbox_pending_total")

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int, {name: 0 for name in self._COUNTERS})
        self._durations: dict[str, list[float]] = defaultdict(
            list, {name: [] for name in self._DURATIONS}
        )
        self._gauges: dict[str, float] = {name: 0 for name in self._GAUGES}

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def observe_seconds(self, name: str, value: float) -> None:
        with self._lock:
            self._durations[name].append(value)

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def snapshot(self) -> dict[str, float | int]:
        """Return a flat export-friendly view of all currently recorded values."""
        with self._lock:
            result: dict[str, float | int] = dict(self._counters)
            result.update(self._gauges)
            for name, values in self._durations.items():
                result[f"{name}_count"] = len(values)
                result[f"{name}_sum"] = sum(values)
            return result


_metrics = TranslationMetrics()


def get_translation_metrics() -> TranslationMetrics:
    """Return the process-wide metrics collector used by production wiring."""
    return _metrics
