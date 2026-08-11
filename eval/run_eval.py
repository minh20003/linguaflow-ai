"""Chấm điểm chất lượng dịch trên Golden Set (F-03.3).

Chạy Translation Agent trên toàn bộ eval/golden_set.jsonl, chấm bằng LLM-as-judge
và ghi kết quả vào eval/results/report.md.

Cách dùng:
    python eval/run_eval.py                 # chạy toàn bộ
    python eval/run_eval.py --limit 5       # chạy thử 5 mẫu đầu
    python eval/run_eval.py --no-write      # in ra màn hình, không ghi report

Yêu cầu: một LLM provider đã cấu hình trong .env (xem LLM_PROVIDER).
Lưu ý: điểm số do LLM tự chấm, không phải đánh giá của người thật.
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

# Cho phép chạy trực tiếp: python eval/run_eval.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.context_provider import InMemoryContextProvider  # noqa: E402
from src.agents.graph import build_translation_graph  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.services.llm import get_llm  # noqa: E402

GOLDEN_SET = Path(__file__).parent / "golden_set.jsonl"
REPORT_PATH = Path(__file__).parent / "results" / "report.md"

# Ngưỡng đạt: điểm judge >= 0.7 coi như bản dịch chấp nhận được
PASS_THRESHOLD = 0.7

JUDGE_PROMPT = """\
Bạn là giám khảo chấm chất lượng dịch thuật. Chấm bản dịch của hệ thống so với \
bản dịch tham chiếu.

Ngôn ngữ nguồn: {source_language}
Ngôn ngữ đích: {target_language}
Câu gốc: {original_text}
Bản dịch tham chiếu: {expected}
Bản dịch của hệ thống: {actual}

Tiêu chí chấm:
- Bảo toàn ý nghĩa so với câu gốc (quan trọng nhất)
- Đúng đại từ nhân xưng và chủ ngữ theo ngữ cảnh
- Giữ nguyên thuật ngữ kỹ thuật, tên riêng, số liệu
- Tự nhiên trong ngôn ngữ đích

Bản dịch không cần trùng khít bản tham chiếu. Khác cách diễn đạt nhưng đúng ý \
vẫn được điểm cao.

Chỉ trả về một số thập phân từ 0.0 đến 1.0, không giải thích, không thêm ký tự nào.\
"""

_SCORE_PATTERN = re.compile(r"[01](?:\.\d+)?")


def load_golden_set(limit: int | None = None) -> list[dict]:
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


async def judge(sample: dict, actual: str) -> float | None:
    """Chấm điểm bản dịch. Trả None nếu không chấm được."""
    prompt = JUDGE_PROMPT.format(
        source_language=sample["source_language"],
        target_language=sample["target_language"],
        original_text=sample["original_text"],
        expected=sample["expected_translation"],
        actual=actual,
    )
    try:
        response = await get_llm().ainvoke(prompt)
        raw = getattr(response, "content", str(response)).strip()
    except Exception as exc:
        print(f"    [!] Judge lỗi: {type(exc).__name__}: {exc}")
        return None

    match = _SCORE_PATTERN.search(raw)
    if not match:
        print(f"    [!] Judge trả về không phải điểm số: {raw[:60]!r}")
        return None

    return min(1.0, max(0.0, float(match.group())))


async def run_sample(sample: dict) -> dict:
    """Chạy agent trên một mẫu và chấm điểm."""
    conversation_id = f"eval-{sample['id']}"

    provider = InMemoryContextProvider()
    for msg in sample.get("context_messages", []):
        provider.add_message(conversation_id, msg)

    graph = build_translation_graph(provider)
    state = await graph.ainvoke(
        {
            "conversation_id": conversation_id,
            "original_text": sample["original_text"],
            "source_language": sample["source_language"],
            "target_language": sample["target_language"],
        }
    )

    actual = state.get("translated_text", "")
    score = await judge(sample, actual)

    return {
        "id": sample["id"],
        "category": sample.get("category", ""),
        "original": sample["original_text"],
        "expected": sample["expected_translation"],
        "actual": actual,
        "score": score,
        "latency_ms": state.get("latency_ms", 0),
        "is_fallback": state.get("is_fallback", False),
    }


def summarize(results: list[dict]) -> dict:
    scored = [r for r in results if r["score"] is not None]
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]

    by_category: dict[str, list[float]] = {}
    for r in scored:
        by_category.setdefault(r["category"], []).append(r["score"])

    return {
        "total": len(results),
        "scored": len(scored),
        "passed": sum(1 for r in scored if r["score"] >= PASS_THRESHOLD),
        "fallback": sum(1 for r in results if r["is_fallback"]),
        "avg_score": statistics.mean([r["score"] for r in scored]) if scored else 0.0,
        "avg_latency": statistics.mean(latencies) if latencies else 0.0,
        "p95_latency": max(latencies) if len(latencies) < 20 else statistics.quantiles(latencies, n=20)[18],
        "by_category": {k: statistics.mean(v) for k, v in sorted(by_category.items())},
    }


def render_report(results: list[dict], summary: dict) -> str:
    settings = get_settings()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    accuracy = summary["passed"] / summary["scored"] * 100 if summary["scored"] else 0

    lines = [
        "# BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG DỊCH",
        "",
        "**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U",
        f"**Thời điểm chạy:** {now}",
        f"**Provider:** {settings.llm_provider} · "
        f"**Model:** {settings.llm_model or 'mặc định của provider'}",
        f"**Bộ dữ liệu:** `eval/golden_set.jsonl` ({summary['total']} mẫu)",
        "",
        "> Điểm số do LLM tự chấm (LLM-as-judge), không phải đánh giá của người thật. "
        "Kết quả dùng để so sánh tương đối giữa các lần chạy và giữa các provider.",
        "",
        "## 1. Chỉ số tổng hợp",
        "",
        "| Chỉ số | Mục tiêu | Thực tế | Trạng thái |",
        "|---|---|---|---|",
        f"| Tỷ lệ đạt (điểm ≥ {PASS_THRESHOLD}) | > 80% | {accuracy:.1f}% | "
        f"{'Đạt' if accuracy > 80 else 'Chưa đạt'} |",
        f"| Điểm trung bình | > 0.80 | {summary['avg_score']:.3f} | "
        f"{'Đạt' if summary['avg_score'] > 0.8 else 'Chưa đạt'} |",
        f"| Độ trễ trung bình | < 1000ms | {summary['avg_latency']:.0f}ms | "
        f"{'Đạt' if summary['avg_latency'] < 1000 else 'Chưa đạt'} |",
        f"| Độ trễ p95 | < 2000ms | {summary['p95_latency']:.0f}ms | "
        f"{'Đạt' if summary['p95_latency'] < 2000 else 'Chưa đạt'} |",
        f"| Số lần fallback | 0 | {summary['fallback']} | "
        f"{'Đạt' if summary['fallback'] == 0 else 'Cần xem lại'} |",
        "",
        "## 2. Điểm theo nhóm tình huống",
        "",
        "| Nhóm | Điểm trung bình |",
        "|---|---|",
    ]

    for category, score in summary["by_category"].items():
        lines.append(f"| `{category}` | {score:.3f} |")

    lines += [
        "",
        "## 3. Chi tiết từng mẫu",
        "",
        "| ID | Nhóm | Điểm | Độ trễ | Câu gốc | Bản dịch hệ thống |",
        "|---|---|---|---|---|---|",
    ]

    for r in results:
        score = f"{r['score']:.2f}" if r["score"] is not None else "—"
        flag = " (fallback)" if r["is_fallback"] else ""
        original = r["original"].replace("|", "\\|")[:45]
        actual = r["actual"].replace("|", "\\|")[:45]
        lines.append(
            f"| {r['id']} | {r['category']} | {score}{flag} | "
            f"{r['latency_ms']}ms | {original} | {actual} |"
        )

    failed = [r for r in results if r["score"] is not None and r["score"] < PASS_THRESHOLD]
    lines += ["", "## 4. Mẫu chưa đạt", ""]
    if not failed:
        lines.append("Không có mẫu nào dưới ngưỡng.")
    else:
        for r in failed:
            lines += [
                f"**{r['id']}** (`{r['category']}`) — điểm {r['score']:.2f}",
                "",
                f"- Câu gốc: {r['original']}",
                f"- Tham chiếu: {r['expected']}",
                f"- Hệ thống: {r['actual']}",
                "",
            ]

    lines += [
        "## 5. Cách tái lập",
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
    parser = argparse.ArgumentParser(description="Chấm điểm Translation Agent")
    parser.add_argument("--limit", type=int, help="Chỉ chạy N mẫu đầu")
    parser.add_argument("--no-write", action="store_true", help="Không ghi report")
    args = parser.parse_args()

    samples = load_golden_set(args.limit)
    print(f"Chạy {len(samples)} mẫu với provider={get_settings().llm_provider}\n")

    results = []
    for i, sample in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] {sample['id']} ({sample.get('category', '')})")
        try:
            result = await run_sample(sample)
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
        REPORT_PATH.write_text(render_report(results, summary), encoding="utf-8")
        print(f"Đã ghi báo cáo: {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
