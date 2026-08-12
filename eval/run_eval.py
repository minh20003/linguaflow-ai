"""Translation quality scoring over the golden set (F-03.3).

Runs the Translation Agent across eval/golden_set.jsonl, scores each sample with
an LLM-as-judge and writes the results to eval/results/report.md.

Usage:
    python eval/run_eval.py                 # run every sample
    python eval/run_eval.py --limit 5       # smoke test on the first 5
    python eval/run_eval.py --no-write      # print only, do not write the report

Requires an LLM provider configured in .env (see LLM_PROVIDER). Scores come from
a model, not from human raters, so they are only comparable between runs.

Each golden-set row carries two classification fields the report breaks results
down by:

* ``chat_type`` — ``direct`` for a bilingual one-to-one thread, ``group`` for a
  thread whose context mixes three or more languages.
* ``context_level`` — ``rich`` when two or more context messages are supplied
  (three or more for group threads), ``poor`` for zero or one. This is the
  supplied-context count, not a judgement about how much context the sentence
  needs.

Speakers in ``context_messages`` are coded ``U01``, ``U02``, ``U03``, numbered in
order of first appearance within each conversation. They carry no name and no
role, because the real ``ContextProvider`` supplies none — ``context_messages``
is a plain ``list[str]`` per docs/CONTRACT.md section 2. Choosing the right
register and pronouns from the conversation alone is the behaviour under test,
so labelling a speaker as a client or a developer would hand the model the
answer. Scenario intent is documented in each row's ``note`` field, which is
never sent to the model.

The generated report is written in Vietnamese: it is a team deliverable, and
project documentation is Vietnamese by convention (see CLAUDE.md).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allows running the file directly: python eval/run_eval.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402

from src.agents.context_provider import InMemoryContextProvider  # noqa: E402
from src.agents.graph import build_translation_graph  # noqa: E402
from src.agents.observability import build_runnable_config  # noqa: E402
from src.config import configure_logging, get_settings  # noqa: E402
from src.services.llm import extract_text, get_llm  # noqa: E402

GOLDEN_SET = Path(__file__).parent / "golden_set.jsonl"
REPORT_PATH = Path(__file__).parent / "results" / "report.md"

# A judge score at or above this counts the translation as acceptable
PASS_THRESHOLD = 0.7

# Report targets. TARGET_LATENCY_MS follows NFR-01 (ARCHITECTURE.md section 5);
# the p95 threshold is an internal convention, not part of the requirements.
TARGET_PASS_RATE = 80.0
TARGET_AVG_SCORE = 0.80
TARGET_LATENCY_MS = 1000
TARGET_P95_LATENCY_MS = 2000

JUDGE_PROMPT = """\
# Role
You are a translation quality judge.

# Task
Score the system translation against the reference translation.

Source language: {source_language}
Target language: {target_language}
Original: {original_text}
Reference translation: {expected}
System translation: {actual}

# Scoring criteria
- Meaning preserved relative to the original (most important)
- Correct pronouns and recovered subjects given the context
- Technical terms, proper nouns and figures kept intact
- Reads naturally in the target language

# Constraints
- The system translation need not match the reference word for word. Different \
wording that carries the same meaning still scores high.
- Return one decimal number between 0.0 and 1.0. No explanation, no other \
characters.\
"""

_SCORE_PATTERN = re.compile(r"[01](?:\.\d+)?")


def load_golden_set(limit: int | None = None) -> list[dict]:
    """Load translation test samples from golden_set.jsonl.

    Args:
        limit: Optional maximum number of samples to load.

    Returns:
        List of sample dictionaries.
    """
    if not GOLDEN_SET.exists():
        raise FileNotFoundError(f"Không tìm thấy golden set: {GOLDEN_SET}")

    samples = []
    with GOLDEN_SET.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Dòng {line_no} không phải JSON hợp lệ: {exc}") from exc

    return samples[:limit] if limit else samples



async def judge(sample: dict, actual: str, judge_llm: BaseChatModel) -> float | None:
    """Score one translation. Returns None when the judge could not score it."""
    prompt = JUDGE_PROMPT.format(
        source_language=sample["source_language"],
        target_language=sample["target_language"],
        original_text=sample["original_text"],
        expected=sample["expected_translation"],
        actual=actual,
    )
    try:
        response = await judge_llm.ainvoke(prompt)
        raw = extract_text(response)
    except Exception as exc:
        print(f"    [!] Judge lỗi: {type(exc).__name__}: {exc}")
        return None

    match = _SCORE_PATTERN.search(raw)
    if not match:
        print(f"    [!] Judge trả về không phải điểm số: {raw[:60]!r}")
        return None

    return min(1.0, max(0.0, float(match.group())))


async def run_sample(
    sample: dict,
    graph,
    provider: InMemoryContextProvider,
    judge_llm: BaseChatModel,
) -> dict:
    """Run the agent on one sample and score the result."""
    conversation_id = f"eval-{sample['id']}"

    for msg in sample.get("context_messages", []):
        provider.add_message(conversation_id, msg)

    state = await graph.ainvoke(
        {
            "conversation_id": conversation_id,
            "original_text": sample["original_text"],
            "source_language": sample["source_language"],
            "target_language": sample["target_language"],
        },
        config=build_runnable_config(
            conversation_id=conversation_id,
            sample_id=sample["id"],
            category=sample.get("category"),
        ),
    )

    actual = state.get("translated_text", "")
    score = await judge(sample, actual, judge_llm)

    return {
        "id": sample["id"],
        "category": sample.get("category", ""),
        "chat_type": sample.get("chat_type", ""),
        "context_level": sample.get("context_level", ""),
        "language_pair": f"{sample['source_language']}->{sample['target_language']}",
        "original": sample["original_text"],
        "expected": sample["expected_translation"],
        "actual": actual,
        "score": score,
        "latency_ms": state.get("latency_ms", 0),
        "is_fallback": state.get("is_fallback", False),
    }


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


def group_scores(scored: list[dict], key: str) -> dict[str, tuple[int, float, int]]:
    """Group scored samples by one field: {value: (count, mean score, passed)}.

    Used for the per-dimension breakdowns (category, chat type, context level,
    language pair) so the report can show where the agent actually degrades
    rather than only a single aggregate number.
    """
    buckets: dict[str, list[float]] = {}
    for r in scored:
        buckets.setdefault(r.get(key) or "(unknown)", []).append(r["score"])

    return {
        value: (
            len(scores),
            statistics.mean(scores),
            sum(1 for s in scores if s >= PASS_THRESHOLD),
        )
        for value, scores in sorted(buckets.items())
    }


def summarize(results: list[dict]) -> dict:
    """Aggregate evaluation scores and latency metrics across test results.

    Args:
        results: List of scored result dictionaries.

    Returns:
        Summary statistics dictionary.
    """
    scored = [r for r in results if r["score"] is not None]
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]

    by_category: dict[str, list[float]] = {}
    for r in scored:
        by_category.setdefault(r["category"], []).append(r["score"])

    return {
        "by_chat_type": group_scores(scored, "chat_type"),
        "by_context_level": group_scores(scored, "context_level"),
        "by_language_pair": group_scores(scored, "language_pair"),
        "total": len(results),
        "scored": len(scored),
        "passed": sum(1 for r in scored if r["score"] >= PASS_THRESHOLD),
        "fallback": sum(1 for r in results if r["is_fallback"]),
        "avg_score": statistics.mean([r["score"] for r in scored]) if scored else 0.0,
        "avg_latency": statistics.mean(latencies) if latencies else 0.0,
        "p95_latency": percentile(latencies, 95),
        "by_category": {k: statistics.mean(v) for k, v in sorted(by_category.items())},
    }


def _metric_rows(summary: dict, accuracy: float) -> list[tuple[str, str, str, bool]]:
    """Metric table rows: label, target, actual value, and whether it passed.

    Each threshold appears once per row so that editing a label cannot leave the
    comparison behind it out of sync.
    """
    return [
        (
            f"Tỷ lệ đạt (điểm ≥ {PASS_THRESHOLD})",
            f"> {TARGET_PASS_RATE:.0f}%",
            f"{accuracy:.1f}%",
            accuracy > TARGET_PASS_RATE,
        ),
        (
            "Điểm trung bình",
            f"> {TARGET_AVG_SCORE:.2f}",
            f"{summary['avg_score']:.3f}",
            summary["avg_score"] > TARGET_AVG_SCORE,
        ),
        (
            "Độ trễ trung bình",
            f"< {TARGET_LATENCY_MS}ms",
            f"{summary['avg_latency']:.0f}ms",
            summary["avg_latency"] < TARGET_LATENCY_MS,
        ),
        (
            "Độ trễ p95",
            f"< {TARGET_P95_LATENCY_MS}ms",
            f"{summary['p95_latency']:.0f}ms",
            summary["p95_latency"] < TARGET_P95_LATENCY_MS,
        ),
        (
            "Số lần fallback",
            "0",
            str(summary["fallback"]),
            summary["fallback"] == 0,
        ),
    ]


def render_report(
    results: list[dict], summary: dict, judge_provider: str | None = None
) -> str:
    """Generate Markdown report for evaluation results.

    Args:
        results: List of scored sample results.
        summary: Aggregated summary statistics.
        judge_provider: Name of the LLM provider used as judge.

    Returns:
        Formatted markdown report string.
    """
    settings = get_settings()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    accuracy = summary["passed"] / summary["scored"] * 100 if summary["scored"] else 0
    judge_name = judge_provider or settings.llm_provider
    is_self_judging = judge_name == settings.llm_provider

    lines = [
        "# BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG DỊCH",
        "",
        "**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U",
        f"**Thời điểm chạy:** {now}",
        f"**Provider dịch:** {settings.llm_provider} · "
        f"**Model:** {settings.llm_model or 'mặc định của provider'}",
        f"**Provider chấm điểm:** {judge_name}",
        f"**Bộ dữ liệu:** `eval/golden_set.jsonl` ({summary['total']} mẫu)",
        "",
        "> Điểm số do LLM tự chấm (LLM-as-judge), không phải đánh giá của người thật. "
        "Kết quả dùng để so sánh tương đối giữa các lần chạy và giữa các provider.",
        "",
    ]

    # Keyed on the providers actually being equal, not on whether the flag was
    # passed: --judge-provider groq with LLM_PROVIDER=groq is still self-judging.
    if is_self_judging:
        lines += [
            "> **CẢNH BÁO:** provider chấm điểm trùng provider dịch — model đang tự "
            "chấm chính nó nên điểm số bị thiên vị. Dùng `--judge-provider` để chỉ "
            "định một model trung lập.",
            "",
        ]

    lines += [
        "## 1. Chỉ số tổng hợp",
        "",
        "| Chỉ số | Mục tiêu | Thực tế | Trạng thái |",
        "|---|---|---|---|",
    ]

    for label, target, actual, is_passed in _metric_rows(summary, accuracy):
        lines.append(f"| {label} | {target} | {actual} | {'Đạt' if is_passed else 'Chưa đạt'} |")


    lines += [
        "",
        "## 2. Điểm theo kiểu hội thoại và độ giàu ngữ cảnh",
        "",
        "Hai chiều này tách riêng vì chúng đo hai năng lực khác nhau: hội thoại nhóm "
        "buộc Agent xử lý ngữ cảnh trộn nhiều ngôn ngữ, còn nhóm nghèo ngữ cảnh đo "
        "khả năng dịch khi không có gì để suy luận thêm.",
        "",
    ]

    for title, key in [
        ("Kiểu hội thoại", "by_chat_type"),
        ("Độ giàu ngữ cảnh", "by_context_level"),
    ]:
        lines += [
            f"**{title}**",
            "",
            f"| {title} | Số mẫu | Điểm trung bình | Tỷ lệ đạt |",
            "|---|---|---|---|",
        ]
        for value, (count, mean_score, passed) in summary[key].items():
            rate = passed / count * 100 if count else 0
            lines.append(f"| `{value}` | {count} | {mean_score:.3f} | {rate:.0f}% |")
        lines.append("")

    lines += [
        "## 3. Điểm theo nhóm tình huống",
        "",
        "| Nhóm | Điểm trung bình |",
        "|---|---|",
    ]

    for category, score in summary["by_category"].items():
        lines.append(f"| `{category}` | {score:.3f} |")

    lines += [
        "",
        "## 4. Điểm theo cặp ngôn ngữ",
        "",
        "| Cặp | Số mẫu | Điểm trung bình | Tỷ lệ đạt |",
        "|---|---|---|---|",
    ]

    for pair, (count, mean_score, passed) in summary["by_language_pair"].items():
        rate = passed / count * 100 if count else 0
        lines.append(f"| `{pair}` | {count} | {mean_score:.3f} | {rate:.0f}% |")

    lines += [
        "",
        "## 5. Chi tiết từng mẫu",
        "",
        "| ID | Kiểu | Ngữ cảnh | Cặp | Nhóm | Điểm | Độ trễ | Câu gốc | Bản dịch hệ thống |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for r in results:
        score = f"{r['score']:.2f}" if r["score"] is not None else "—"
        flag = " (fallback)" if r["is_fallback"] else ""
        original = r["original"].replace("|", "\\|")[:45]
        actual = r["actual"].replace("|", "\\|")[:45]
        lines.append(
            f"| {r['id']} | {r['chat_type']} | {r['context_level']} | "
            f"{r['language_pair']} | {r['category']} | {score}{flag} | "
            f"{r['latency_ms']}ms | {original} | {actual} |"
        )

    failed = [r for r in results if r["score"] is not None and r["score"] < PASS_THRESHOLD]
    lines += ["", "## 6. Mẫu chưa đạt", ""]
    if not failed:
        lines.append("Không có mẫu nào dưới ngưỡng.")
    else:
        for r in failed:
            lines += [
                f"**{r['id']}** (`{r['category']}`, {r['chat_type']}, "
                f"ngữ cảnh {r['context_level']}, {r['language_pair']}) — "
                f"điểm {r['score']:.2f}",
                "",
                f"- Câu gốc: {r['original']}",
                f"- Tham chiếu: {r['expected']}",
                f"- Hệ thống: {r['actual']}",
                "",
            ]

    lines += [
        "## 7. Cách tái lập",
        "",
        "```bash",
        "python eval/run_eval.py",
        "```",
        "",
        "Đổi provider bằng biến `LLM_PROVIDER` trong `.env` rồi chạy lại để so sánh.",
        "",
    ]

    return "\n".join(lines)


async def main() -> int:
    """Run translation evaluation suite and output report.

    Returns:
        Exit code (0 on success, 1 on failure).
    """
    parser = argparse.ArgumentParser(description="Chấm điểm Translation Agent")

    parser.add_argument("--limit", type=int, help="Chỉ chạy N mẫu đầu")
    parser.add_argument("--no-write", action="store_true", help="Không ghi report")
    parser.add_argument(
        "--judge-provider",
        help=(
            "Provider dùng để chấm điểm. Nên đặt khác provider đang dịch, nếu không "
            "model sẽ tự chấm chính nó và điểm bị thiên vị."
        ),
    )
    args = parser.parse_args()

    # This harness drives the graph without going through src/main.py, so it has
    # to configure logging itself or the agent's fallback records are discarded.
    configure_logging()

    samples = load_golden_set(args.limit)
    translate_provider = get_settings().llm_provider
    judge_name = args.judge_provider or translate_provider
    print(
        f"Chạy {len(samples)} mẫu · dịch={translate_provider} · chấm={judge_name}"
        + ("  [CẢNH BÁO: model tự chấm chính nó]" if judge_name == translate_provider else "")
        + "\n"
    )

    # Built once for the whole run: the configuration is identical across samples,
    # and InMemoryContextProvider already partitions by conversation_id.
    context_provider = InMemoryContextProvider()
    graph = build_translation_graph(context_provider)
    judge_llm = get_llm(provider=args.judge_provider)

    results = []
    for i, sample in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] {sample['id']} ({sample.get('category', '')})")
        try:
            result = await run_sample(sample, graph, context_provider, judge_llm)
        except Exception as exc:
            print(f"    [!] Lỗi: {type(exc).__name__}: {exc}")
            continue

        score = f"{result['score']:.2f}" if result["score"] is not None else "—"
        print(f"    điểm={score} latency={result['latency_ms']}ms")
        results.append(result)

    if not results:
        print("\nKhông chạy được mẫu nào. Kiểm tra cấu hình LLM trong .env.")
        return 1

    summary = summarize(results)
    print(
        f"\nTổng kết: {summary['passed']}/{summary['scored']} đạt · "
        f"điểm TB {summary['avg_score']:.3f} · "
        f"latency TB {summary['avg_latency']:.0f}ms · "
        f"fallback {summary['fallback']}"
    )

    if not args.no_write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            render_report(results, summary, args.judge_provider), encoding="utf-8"
        )
        print(f"Đã ghi báo cáo: {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
