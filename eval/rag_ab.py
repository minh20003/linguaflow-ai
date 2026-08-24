"""Does retrieval change the translation? Measured end to end, per embedding model.

`rag_sweep.py` answers whether retrieval can *find* the line that matters. This
answers the question that decides whether the feature ships: when it finds it,
does the translation get better. Finding the right line is a necessary
condition, never a sufficient one — a model handed the right context can still
ignore it.

Every scenario runs twice against the same seeded conversation, once with
`RAG_CONTEXT_ENABLED` off and once on, and is scored three ways:

- the **LLM judge**, the same one `run_eval.py` uses, for "is this acceptable";
- **hard metrics** — chrF++, BLEU, TER — which are deterministic, so a movement
  here is a movement in the output rather than in the judge's mood (ADR-17);
- **retrieval and generation metrics** — was the decisive line actually pulled
  in, did the output stay in the target language, did it smuggle in history the
  message never said.

Three categories, because the team is choosing a strategy and the three do not
have to move together:

- ``elision`` — a dropped subject or referent, the textbook retrieval case.
- ``term`` — a wording this conversation agreed on long ago. This is the
  glossary case *before* it reaches the glossary: a convention that lives in the
  thread and nowhere else, which only retrieval can supply.
- ``honorific`` — an old exchange establishing how these two address each other.
  Whether retrieval helps here matters because the standing enum (ADR-23) is
  inferred from exactly this kind of evidence.

The conversation, its filler and its length are shared with `rag_sweep.py` so
the two measurements describe the same world.

    python eval/rag_ab.py                          # every model below
    python eval/rag_ab.py --models gemini:models/gemini-embedding-2
    python eval/rag_ab.py --keep                   # leave the rows behind
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics import (  # noqa: E402
    bleed_score,
    in_target_language,
    score_translation,
)
from rag_sweep import _cleanup, _parse_model, _seed  # noqa: E402
from run_eval import JUDGE_PROMPT, parse_score  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.agents.graph import build_translation_graph  # noqa: E402
from src.agents.prompts import build_context_block  # noqa: E402
from src.config import configure_logging, get_settings  # noqa: E402
from src.database.models import EMBEDDING_DIM  # noqa: E402
from src.services.context_provider import DatabaseContextProvider  # noqa: E402
from src.services.embeddings import embed  # noqa: E402
from src.services.llm import extract_text, get_llm  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results" / "rag"

# Only 768-dimension models can be measured through this path at all: the
# `message_embeddings.embedding` column is `vector(768)` and rejects anything
# else outright. `paraphrase-multilingual-MiniLM-L12-v2` returns 384, so it
# cannot be scored here without a migration and a pass to re-embed everything —
# a schema decision, not an evaluation setting (ADR-25).
DEFAULT_MODELS = [
    "gemini:models/gemini-embedding-2",
    "local:intfloat/multilingual-e5-base",
    "local:sentence-transformers/LaBSE",
]

SCENARIOS = [
    # ---- elision: the textbook case, a subject or referent left out ----
    {
        "name": "import-done",
        "category": "elision",
        "anchor": "Em nhận phần import dữ liệu CSV cho màn hình khách hàng nhé",
        "message": "Đã xong rồi nhé",
        "source_language": "vi",
        "target_language": "en",
        "expected": "The CSV import is done",
    },
    {
        "name": "plan-approved",
        "category": "elision",
        "anchor": "Bên mình thống nhất chọn phương án B cho hợp đồng bảo trì",
        "message": "Cái đó bên anh duyệt chưa?",
        "source_language": "vi",
        "target_language": "en",
        "expected": "Have you approved the maintenance plan yet?",
    },
    {
        "name": "reviewer-replied",
        "category": "elision",
        "anchor": "Chị Lan bên QA sẽ là người rà soát bản build này",
        "message": "Bạn ấy phản hồi chưa?",
        "source_language": "vi",
        "target_language": "en",
        "expected": "Has she replied yet?",
    },
    # ---- term: a wording this conversation settled on, and nowhere else ----
    {
        "name": "dashboard-label",
        "category": "term",
        "anchor": "Chốt gọi màn hình đó là Trang tổng quan chứ không dùng chữ Dashboard nữa",
        "message": "Please update the Dashboard label before the demo",
        "source_language": "en",
        "target_language": "vi",
        "expected": "Cập nhật nhãn Trang tổng quan trước buổi demo nhé",
    },
    {
        "name": "release-word",
        "category": "term",
        "anchor": "Trong tài liệu cho khách mình gọi release là bản phát hành nhé",
        "message": "The release notes are ready for review",
        "source_language": "en",
        "target_language": "vi",
        "expected": "Ghi chú bản phát hành đã sẵn sàng để rà soát",
    },
    {
        "name": "ticket-word",
        "category": "term",
        "anchor": "Bên khách quen gọi ticket là yêu cầu hỗ trợ, mình dùng theo họ",
        "message": "Can you close the ticket after testing?",
        "source_language": "en",
        "target_language": "vi",
        "expected": "Sau khi kiểm thử xong đóng yêu cầu hỗ trợ giúp mình nhé",
    },
    # ---- honorific: an old exchange that establishes who stands where ----
    {
        "name": "senior-established",
        "category": "honorific",
        "anchor": "Dạ anh Minh, em là người mới, có gì anh chỉ em thêm ạ",
        "message": "Could you take a look when you have time?",
        "source_language": "en",
        "target_language": "vi",
        "expected": "Khi nào anh rảnh xem giúp em với ạ",
    },
    {
        "name": "junior-established",
        "category": "honorific",
        "anchor": "Em mới vào nên phần này anh giao cho em làm trước nhé",
        "message": "Could you take a look when you have time?",
        "source_language": "en",
        "target_language": "vi",
        "expected": "Lúc nào rảnh em xem giúp anh nhé",
    },
    {
        "name": "client-established",
        "category": "honorific",
        "anchor": "Bên quý khách gửi yêu cầu qua email, mình sẽ phản hồi trong ngày",
        "message": "Could you take a look when you have time?",
        "source_language": "en",
        "target_language": "vi",
        "expected": "Mong quý khách xem giúp khi có thời gian ạ",
    },
]


async def _translate(session, scenario: dict, conversation_id: str, message_id: str) -> dict:
    """Run the real graph over the real provider, and report what it saw."""
    provider = DatabaseContextProvider(session, before_message_id=message_id)
    graph = build_translation_graph(provider)
    state = await graph.ainvoke(
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "original_text": scenario["message"],
            "source_language": scenario["source_language"],
            "target_language": scenario["target_language"],
        }
    )
    return {
        "translated_text": state.get("translated_text", ""),
        "context_messages": state.get("context_messages", []),
        "latency_ms": state.get("latency_ms", 0),
        "is_fallback": state.get("is_fallback", False),
    }


async def _judge(scenario: dict, actual: str, judge_llm, context_lines: list[str]):
    """Score one translation exactly as `run_eval` scores everything else."""
    prompt = JUDGE_PROMPT.format(
        source_language=scenario["source_language"],
        target_language=scenario["target_language"],
        context_block=build_context_block(context_lines),
        original_text=scenario["message"],
        expected=scenario["expected"],
        actual=actual,
    )
    try:
        return parse_score(extract_text(await judge_llm.ainvoke(prompt)))
    except Exception as exc:
        print(f"    [!] Judge lỗi: {type(exc).__name__}: {exc}")
        return None


def _mean(values: list) -> float:
    """Mean of the values that exist, 0.0 when none do."""
    present = [v for v in values if v is not None]
    return statistics.mean(present) if present else 0.0


def _report(rows: list[dict]) -> None:
    """Print the comparison the team decides on, split by category.

    Leads with the fallback count, because that number decides whether the rest
    of the table means anything. A failed LLM call degrades to the secondary
    provider by design (NFR-02), and that provider is deterministic — so a run
    where everything fell back produces identical scores for every mode and
    every embedding model, which reads as "retrieval changes nothing" when it
    actually means "the model under test never ran".
    """
    fallbacks = sum(1 for r in rows if r["is_fallback"])
    if fallbacks:
        print(
            f"\n[!] {fallbacks}/{len(rows)} bản dịch đến từ tầng dự phòng, "
            "không phải từ model đang đo."
            + (
                " Toàn bộ bảng dưới đây là số của deep-translator — kiểm tra "
                "LLM_MODEL trước khi đọc tiếp."
                if fallbacks == len(rows)
                else ""
            )
        )
    for embedding in dict.fromkeys(r["embedding"] for r in rows):
        print(f"\n=== {embedding}")
        for category in ("elision", "term", "honorific", "TẤT CẢ"):
            picked = [
                r
                for r in rows
                if r["embedding"] == embedding
                and (category == "TẤT CẢ" or r["category"] == category)
            ]
            if not picked:
                continue
            print(f"  {category}  (n={len(picked) // 2})")
            for mode in ("off", "on"):
                side = [r for r in picked if r["mode"] == mode]
                if not side:
                    continue
                hits = sum(1 for r in side if r["anchor_retrieved"])
                print(
                    f"    RAG {mode:3}: judge={_mean([r['score'] for r in side]):.2f} "
                    f"chrF++={_mean([r['chrf'] for r in side]):5.1f} "
                    f"BLEU={_mean([r['bleu'] for r in side]):5.1f} "
                    f"TER={_mean([r['ter'] for r in side]):5.1f} "
                    f"rò={_mean([r['bleed'] for r in side]):.3f} "
                    f"đúng ngôn ngữ={_mean([1.0 if r['in_target'] else 0.0 for r in side]):.0%}"
                    f" · tìm được dòng quyết định {hits}/{len(side)}"
                    f" · {_mean([r['latency_ms'] for r in side]):.0f}ms"
                )


async def main() -> int:
    """Seed once per embedding model, then translate every scenario both ways."""
    parser = argparse.ArgumentParser(description="RAG bật/tắt trên hội thoại dài")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--keep", action="store_true", help="Không xoá dữ liệu đã seed")
    parser.add_argument("--no-write", action="store_true", help="Không lưu kết quả")
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    judge_llm = get_llm(
        provider=settings.llm_judge_provider or None,
        model=settings.judge_model or None,
    )

    print(
        f"dịch={settings.llm_provider}/{settings.llm_model or 'mặc định'} · "
        f"chấm={settings.llm_judge_provider or settings.llm_provider}"
        f"/{settings.judge_model or 'mặc định'} · "
        f"{len(SCENARIOS)} kịch bản × 2 chế độ\n"
    )

    rows: list[dict] = []
    for spec in args.models:
        provider, model = _parse_model(spec)
        object.__setattr__(settings, "embedding_provider", provider)
        object.__setattr__(settings, "embedding_model", model)
        label = f"{provider}:{model or 'mặc định'}"

        # Checked before anything is seeded, and through `embed` rather than the
        # paced wrapper: a width mismatch is refused by `embed` itself, and the
        # wrapper would read that refusal as a rate limit and sit out a quota
        # window before failing. A model of the wrong width also fails on the
        # first insert with a column error that explains nothing, by which point
        # the run has already spent its embedding quota.
        if await embed("kiểm tra chiều vector") is None:
            print(
                f"[bỏ qua] {label}: không lấy được vector {EMBEDDING_DIM} chiều. "
                "Model sai số chiều thì cần một migration và một lượt embed lại "
                "toàn bộ, đó là quyết định về schema chứ không phải tham số đo."
            )
            continue

        print(f"--- seed {label}")
        conversation_ids: list[str] = []
        try:
            seeded = []
            async with factory() as session:
                for scenario in SCENARIOS:
                    conversation_id, message_id, _, _ = await _seed(session, scenario)
                    conversation_ids.append(conversation_id)
                    seeded.append((scenario, conversation_id, message_id))

            for scenario, conversation_id, message_id in seeded:
                for mode, enabled in (("off", False), ("on", True)):
                    object.__setattr__(settings, "rag_context_enabled", enabled)
                    async with factory() as session:
                        result = await _translate(
                            session, scenario, conversation_id, message_id
                        )
                    actual = result["translated_text"]
                    mt = score_translation(
                        actual,
                        scenario["expected"],
                        target_language=scenario["target_language"],
                    )
                    rows.append(
                        {
                            "embedding": label,
                            "mode": mode,
                            "scenario": scenario["name"],
                            "category": scenario["category"],
                            "actual": actual,
                            "expected": scenario["expected"],
                            "score": await _judge(
                                scenario, actual, judge_llm, result["context_messages"]
                            ),
                            "chrf": round(mt.chrf, 2) if mt else None,
                            "bleu": round(mt.bleu, 2) if mt else None,
                            "ter": round(mt.ter, 2) if mt else None,
                            "bleed": round(
                                bleed_score(
                                    actual,
                                    source=scenario["message"],
                                    context_lines=result["context_messages"],
                                ),
                                4,
                            ),
                            "in_target": in_target_language(
                                actual, scenario["target_language"]
                            ),
                            "anchor_retrieved": any(
                                scenario["anchor"] in line
                                for line in result["context_messages"]
                            ),
                            "context_lines": len(result["context_messages"]),
                            "latency_ms": result["latency_ms"],
                            "is_fallback": result["is_fallback"],
                        }
                    )
        finally:
            if not args.keep:
                await _cleanup(factory, conversation_ids)

    _report(rows)

    if not args.no_write and rows:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = RESULTS_DIR / f"ab-{run_id}.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "translate_provider": settings.llm_provider,
                    "translate_model": settings.llm_model,
                    "judge_provider": settings.llm_judge_provider,
                    "judge_model": settings.judge_model,
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nĐã lưu: {path}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
