"""Measure the assistant's chunking and retrieval strategies against each other.

    python eval/assistant_chunk_sweep.py --tier XS --offline      # no provider, proves the pipeline
    python eval/assistant_chunk_sweep.py --tier M,L
    python eval/assistant_chunk_sweep.py --tier L --strategy turn_window,token_window
    python eval/assistant_chunk_sweep.py --tier L --embedding local:intfloat/multilingual-e5-base

Answers the question ADR-38 is waiting on: which way of cutting a conversation
into chunks actually finds the messages that hold the answer. Every strategy is
scored **per message rather than per chunk**, because `message` produces 800
chunks for the L tier and `turn_window` about 150 — counting chunks would make
them incomparable by construction.

The gate this exists to check: **recall@4 >= 70% at tier L**, against the 22%
`sweep-20260822-064517` measured for the message-level index the translation
agent uses. Every figure is printed beside a chance baseline, because a recall
number on its own cannot be read.

**Cost.** Each run embeds every chunk of every strategy. For XL that is roughly
ten thousand embedding calls, and Gemini's free tier is twenty a day — use
`--embedding local:...` for anything above tier M, and `--offline` when what is
being checked is the harness rather than a model.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import assistant_metrics  # noqa: E402
from build_assistant_corpus import (  # noqa: E402
    CorpusDocument,
    load,
    seed_tier,
)
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import configure_logging, get_settings  # noqa: E402
from src.database.models import (  # noqa: E402
    ASSISTANT_CHUNK_STRATEGIES,
    AssistantChunk,
    Message,
)
from src.services import assistant_indexing, assistant_retrieval  # noqa: E402
from src.services.assistant_retrieval import RetrievalConfig  # noqa: E402
from src.services.embeddings import with_embedding  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results" / "assistant"

# The cut-off the gate is stated at. Four chunks is what `ASSISTANT_RERANK_TOP_N`
# puts in front of the model, so recall@4 is the number that decides whether the
# answer was reachable at all.
GATE_K = 4
GATE_RECALL = 0.70

# Retrieval arrangements to compare. Each isolates one layer, so the table says
# what each contributes rather than only what the whole stack scores. Reranking
# is left out of the default sweep: the cross-encoder pulls torch into the
# process and reorders a list this measurement is trying to see unreordered.
ARRANGEMENTS: dict[str, dict] = {
    "vector": {"use_lexical": False, "use_rerank": False},
    "hybrid": {"use_lexical": True, "use_rerank": False},
    "hybrid+rerank": {"use_lexical": True, "use_rerank": True},
}


def _offline_vector(text: str) -> list[float]:
    """A deterministic embedding with no provider behind it.

    Hashes character trigrams into 768 buckets. It has no semantics whatsoever,
    so the numbers it produces are meaningless as a measure of retrieval — its
    only job is to prove the harness runs end to end: indexing, the two query
    arms, fusion, scoring, and the report. Runs with this are marked `offline`
    in the result file so nobody reads them as a measurement later.
    """
    vector = [0.0] * 768
    lowered = (text or "").casefold()
    for position in range(max(len(lowered) - 2, 0)):
        gram = lowered[position : position + 3]
        bucket = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16) % 768
        vector[bucket] += 1.0
    return vector or [0.1] * 768


def _install_offline_embeddings() -> None:
    """Point both the write and the read path at `_offline_vector`."""

    async def fake_embed(text, *, settings=None):
        return _offline_vector(text)

    assistant_indexing.embed = fake_embed
    assistant_retrieval.embed = fake_embed
    assistant_indexing.embedding_model_name = lambda settings=None: "offline-trigram"
    assistant_retrieval.embedding_model_name = lambda settings=None: "offline-trigram"


async def _message_ids_by_index(session, conversation_id: str) -> list[str]:
    """Map each corpus index back to the message id it was seeded as.

    The corpus labels answers by index; retrieval returns message ids. This is
    the join between them, and it is read from the database rather than
    reconstructed, so a seeding change cannot silently misalign the answer key.
    """
    rows = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    return [row.id for row in rows.all()]


async def sweep_tier(
    document: CorpusDocument,
    *,
    strategies: list[str],
    arrangements: list[str],
    top_k: int,
    top_n: int,
) -> list[dict]:
    """Index and measure one tier under every strategy and arrangement."""
    engine = create_async_engine(get_settings().database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    conversation_id = await seed_tier(document)
    print(f"  seeded conversation {conversation_id}")

    rows: list[dict] = []
    try:
        async with session_maker() as session:
            ids_by_index = await _message_ids_by_index(session, conversation_id)

            # Queries with nothing planted are excluded from retrieval scoring.
            # A `negative` query has no right answer to find, so recall over it
            # is undefined; whether the assistant refuses is a generation
            # measurement and belongs to `run_assistant_eval.py`.
            scored_queries = [
                query for query in document.queries if query.relevant_indexes
            ]

            for strategy in strategies:
                started = time.perf_counter()
                chunk_count = await assistant_indexing.index_conversation(
                    session, conversation_id=conversation_id, strategy=strategy
                )
                index_ms = (time.perf_counter() - started) * 1000

                searchable = (
                    await session.scalar(
                        select(AssistantChunk.id)
                        .where(
                            AssistantChunk.conversation_id == conversation_id,
                            AssistantChunk.strategy == strategy,
                            AssistantChunk.embedding.is_not(None),
                        )
                        .limit(1)
                    )
                ) is not None
                if not searchable:
                    print(f"  {strategy}: nothing embedded, skipping")
                    continue

                for arrangement in arrangements:
                    config = RetrievalConfig(
                        strategy=strategy,
                        top_k=top_k,
                        top_n=top_n,
                        **ARRANGEMENTS[arrangement],
                    )
                    per_query: list[assistant_metrics.RetrievalScores] = []
                    by_kind: dict[str, list[float]] = {}
                    query_ms: list[float] = []

                    for query in scored_queries:
                        relevant = [
                            ids_by_index[index]
                            for index in query.relevant_indexes
                            if index < len(ids_by_index)
                        ]
                        started = time.perf_counter()
                        results = await assistant_retrieval.retrieve(
                            session,
                            conversation_id=conversation_id,
                            query_text=query.question,
                            config=config,
                        )
                        query_ms.append((time.perf_counter() - started) * 1000)

                        score = assistant_metrics.score_retrieval(
                            [list(result.message_ids) for result in results],
                            relevant,
                            k=top_n,
                        )
                        per_query.append(score)
                        by_kind.setdefault(query.kind, []).append(score.recall)

                    chance_hit, chance_recall = assistant_metrics.chance_baseline(
                        chunk_count=chunk_count,
                        relevant_count=max(
                            (len(query.relevant_indexes) for query in scored_queries),
                            default=1,
                        ),
                        k=top_n,
                    )

                    rows.append(
                        {
                            "tier": document.tier,
                            "strategy": strategy,
                            "arrangement": arrangement,
                            "chunks": chunk_count,
                            "queries": len(per_query),
                            "recall": round(
                                assistant_metrics.mean([s.recall for s in per_query]), 3
                            ),
                            "precision": round(
                                assistant_metrics.mean([s.precision for s in per_query]), 3
                            ),
                            "ndcg": round(
                                assistant_metrics.mean([s.ndcg for s in per_query]), 3
                            ),
                            "mrr": round(
                                assistant_metrics.mean(
                                    [s.reciprocal_rank for s in per_query]
                                ),
                                3,
                            ),
                            "hit_rate": round(
                                assistant_metrics.mean(
                                    [1.0 if s.hit else 0.0 for s in per_query]
                                ),
                                3,
                            ),
                            "chance_recall": round(chance_recall, 3),
                            "chance_hit_rate": round(chance_hit, 3),
                            "recall_by_kind": {
                                kind: round(assistant_metrics.mean(values), 3)
                                for kind, values in sorted(by_kind.items())
                            },
                            "index_ms": round(index_ms),
                            "query_ms": round(assistant_metrics.mean(query_ms)),
                        }
                    )
                    row = rows[-1]
                    print(
                        f"  {strategy:15} {arrangement:14} "
                        f"chunks={row['chunks']:5} "
                        f"recall@{top_n}={row['recall']:.0%} "
                        f"nDCG={row['ndcg']:.3f} MRR={row['mrr']:.3f} "
                        f"· chance recall={row['chance_recall']:.1%}"
                    )
    finally:
        await engine.dispose()

    return rows


def _render(rows: list[dict], *, offline: bool) -> str:
    """A table, then the gate verdict."""
    lines = ["", "| bậc | chiến lược | cách truy hồi | chunk | recall@4 | nDCG | MRR | ngẫu nhiên |", "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row['tier']} | `{row['strategy']}` | {row['arrangement']} | "
            f"{row['chunks']} | **{row['recall']:.0%}** | {row['ndcg']:.3f} | "
            f"{row['mrr']:.3f} | {row['chance_recall']:.1%} |"
        )

    lines.append("")
    if offline:
        lines.append(
            "⚠️  Chạy ở chế độ `--offline`: vector do hàm băm trigram sinh ra, "
            "không mang ngữ nghĩa nào. Bảng này chỉ chứng minh harness chạy đúng, "
            "**không phải một phép đo**."
        )
        return "\n".join(lines)

    gated = [row for row in rows if row["tier"] == "L"]
    if not gated:
        lines.append("Chưa chạy bậc L nên chưa kết luận được về ngưỡng.")
        return "\n".join(lines)

    best = max(gated, key=lambda row: row["recall"])
    verdict = "ĐẠT" if best["recall"] >= GATE_RECALL else "CHƯA ĐẠT"
    lines.append(
        f"**Ngưỡng recall@{GATE_K} ≥ {GATE_RECALL:.0%} ở bậc L: {verdict}.** "
        f"Tốt nhất là `{best['strategy']}` + {best['arrangement']} "
        f"= {best['recall']:.0%} (so với 22% của chỉ mục mức tin nhắn)."
    )
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", default="M", help="Các bậc, phân tách bằng dấu phẩy")
    parser.add_argument(
        "--strategy",
        default=",".join(ASSISTANT_CHUNK_STRATEGIES),
        help="Chiến lược chunk cần đo",
    )
    parser.add_argument(
        "--arrangement",
        default="vector,hybrid",
        help=f"Cách truy hồi: {', '.join(ARRANGEMENTS)}",
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--top-n", type=int, default=GATE_K)
    parser.add_argument(
        "--embedding",
        default="",
        help="Ghi đè model nhúng dạng provider:model, ví dụ local:intfloat/multilingual-e5-base",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Dùng vector băm trigram, không gọi provider. Chứng minh harness, không phải phép đo.",
    )
    parser.add_argument("--no-write", action="store_true", help="Không ghi kết quả")
    args = parser.parse_args()

    configure_logging()

    if args.offline:
        _install_offline_embeddings()
    elif args.embedding:
        provider, _, model = args.embedding.partition(":")
        settings = get_settings()
        overridden = with_embedding(settings, provider, model)
        # Both paths read the settings they are handed; the retrieval path
        # resolves the assistant's own pair, so it is pointed at the override
        # here rather than left to read the process configuration.
        assistant_indexing.assistant_embedding_settings = lambda s=None: overridden
        assistant_retrieval.assistant_embedding_settings = lambda s=None: overridden

    strategies = [name.strip() for name in args.strategy.split(",") if name.strip()]
    unknown = [name for name in strategies if name not in ASSISTANT_CHUNK_STRATEGIES]
    if unknown:
        print(f"Chiến lược không hợp lệ: {', '.join(unknown)}", file=sys.stderr)
        return 2

    arrangements = [name.strip() for name in args.arrangement.split(",") if name.strip()]
    unknown = [name for name in arrangements if name not in ARRANGEMENTS]
    if unknown:
        print(f"Cách truy hồi không hợp lệ: {', '.join(unknown)}", file=sys.stderr)
        return 2

    rows: list[dict] = []
    for tier in [name.strip().upper() for name in args.tier.split(",") if name.strip()]:
        try:
            document = load(tier)
        except FileNotFoundError:
            print(
                f"Chưa dựng bậc {tier}. Chạy: python eval/build_assistant_corpus.py --tier {tier}",
                file=sys.stderr,
            )
            return 2
        print(f"\n{tier} · {len(document.messages)} tin · {len(document.queries)} câu hỏi")
        rows.extend(
            await sweep_tier(
                document,
                strategies=strategies,
                arrangements=arrangements,
                top_k=args.top_k,
                top_n=args.top_n,
            )
        )

    report = _render(rows, offline=args.offline)
    print(report)

    if not args.no_write and rows:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = RESULTS_DIR / f"sweep-{run_id}.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "offline": args.offline,
                    "embedding_override": args.embedding,
                    "top_k": args.top_k,
                    "top_n": args.top_n,
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"\n→ {path}")
        print("Nhớ chạy `python eval/build_assistant_corpus.py --cleanup` khi xong.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
