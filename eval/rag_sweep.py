"""Sweep embedding model against query strategy, and score the retrieval.

`eval/rag_ab.py` answers "is retrieval worth turning on" for one configuration
and pays for a translation and a judge call to do it. This answers the question
underneath that one — *which* configuration — and does it without calling a
chat model at all. Retrieval either returns the line that mattered or it does
not, and that is checkable against the seeded conversation for free.

Two axes:

**Embedding model.** Whatever `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL` name. Each
one is seeded into its own conversations, because vectors from two models are
not comparable and mixing them in one table would return a confident wrong
answer rather than an error.

**Query strategy** — what gets embedded to search *with*. Production embeds the
message alone, and `rag_ab.py` measured why that is the weak point: the messages
that most need older context are the short elliptical ones, whose nearest
neighbours are other short chit-chat. The alternatives widen the query:

- ``message`` — the message on its own. What ships today.
- ``message_plus_previous`` — the message and the single line before it. The
  smallest possible widening: enough to give an elliptical message a subject to
  be about, without handing the query over to whatever else was being discussed.
- ``message_plus_recent`` — the message joined with the whole recent window,
  embedded as one text. The proposal that came out of `rag_ab.py`.
- ``recent_only`` — the window without the message. A control: if it matches
  ``message_plus_recent``, the message contributed nothing and the window is
  deciding the query on its own.

The last two cost an embedding call **on the request path**, which the current
design deliberately avoids by reusing the vector written in the background when
the message arrived. That cost is measured here and reported beside the quality,
because it comes straight out of the NFR-01 budget.

Every run is written to `eval/results/rag/` so configurations can be compared
later without paying for them again.

    python eval/rag_sweep.py                      # every model, every strategy
    python eval/rag_sweep.py --models local:...   # just one embedding model
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics import score_retrieval  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import configure_logging, get_settings  # noqa: E402
from src.database.models import (  # noqa: E402
    Conversation,
    ConversationMember,
    Message,
    MessageEmbedding,
    User,
)
from src.services.embeddings import embed  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results" / "rag"

# Embedding configurations to sweep, as `provider:model`. An empty model means
# the provider default.
#
# Both local models are multilingual, and only multilingual ones belong here: a
# Vietnamese-specialised model scores well on a Vietnamese test set and then has
# nothing to say about the Japanese and English half of the same thread, which
# is the situation this product is *for*. `multilingual-e5-base` is the one of
# the two actually tuned for retrieval rather than for sentence similarity, and
# it is measured here the way production would use it — without the "query:" /
# "passage:" prefixes its authors recommend, because nothing in
# `context_provider.py` adds them.
#
# Groq serves no embedding endpoint at all (403 on `/embeddings`); the OpenAI
# key on this project has no quota.
DEFAULT_MODELS = [
    "gemini:models/gemini-embedding-2",
    "local:sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "local:intfloat/multilingual-e5-base",
]

STRATEGIES = ("message", "message_plus_previous", "message_plus_recent", "recent_only")

# Filler long enough to push the anchor out of a five-message window, and
# deliberately mundane: office small talk is what really sits between a decision
# and the message that refers back to it.
# A long thread, not a handful of lines. RAG exists for "something agreed forty
# messages ago", and a twelve-message conversation cannot pose that question:
# with six candidates a random retriever already scores 50% at hit@3, so nothing
# measured on one is distinguishable from luck.
#
# Mixed vi / en / ja on purpose. A same-language corpus lets an embedding model
# score well by matching script and vocabulary, which is exactly the shortcut
# that disappears in this product's real threads. The filler is also not pure
# small talk — most of it is ordinary project chatter about *other* subjects,
# which is harder and fairer than the off-topic filler the first version used.
FILLER = [
    "U01: Sáng nay mình sẽ review PR của phần thanh toán trước",
    "U02: I pushed the fix for the login redirect last night",
    "U03: 了解しました、こちらでも確認します",
    "U01: Bên QA báo còn hai lỗi nhỏ ở màn hình danh sách",
    "U02: Are those blocking the release or can they wait?",
    "U03: 明日のミーティングは10時からでよろしいですか",
    "U01: 10h nhé, mình sẽ gửi lịch qua email",
    "U02: The staging deploy finished but the cache was not cleared",
    "U03: キャッシュのクリアは手動でやる必要がありますね",
    "U01: Mình vừa clear cache rồi, mọi người thử lại giúp",
    "U02: Works now, thanks",
    "U03: 請求書のテンプレートを更新しました",
    "U01: Template mới trông ổn, mình sẽ gửi cho khách xem",
    "U02: Do we need translations for the error messages too?",
    "U03: エラーメッセージは後回しでいいと思います",
    "U01: Ừ để sau, ưu tiên phần đăng nhập trước đã",
    "U02: I will start on the export feature tomorrow",
    "U03: エクスポートはCSVだけで十分でしょうか",
    "U01: CSV trước đã, Excel để phase sau",
    "U02: Sounds good",
    "U03: 今週の進捗レポートを共有します",
    "U01: Cảm ơn, mình sẽ đọc trong chiều nay",
    "U02: The client asked about the timeline again",
    "U03: スケジュールは来週更新する予定です",
    "U01: Mình sẽ trả lời khách sau khi có lịch mới",
    "U02: Anyone knows why the tests are slow on CI?",
    "U03: データベースのマイグレーションが毎回走っているからです",
    "U01: Để mình xem lại config của CI",
    "U02: I added a cache step, should be faster now",
    "U03: 助かります",
    "U01: Chiều nay mình off sớm một chút nhé",
    "U02: No problem, see you tomorrow",
    "U03: お疲れさまでした",
    "U01: Sáng mai mình sẽ họp với bên thiết kế",
    "U02: Let me know if they change the layout again",
    "U03: レイアウトの変更は最小限にしてほしいですね",
    "U01: Mình sẽ đề nghị giữ nguyên bố cục hiện tại",
    "U02: Agreed",
]

# Nine scenarios rather than three: a hit rate over three cases moves in steps
# of 33 points, which cannot distinguish a better configuration from a luckier
# one. Each is an elided subject or referent — never a fact the translation
# should state, which would be a defect however good retrieval was.
SCENARIOS = [
    {
        "name": "import-done",
        "anchor": "Em nhận phần import dữ liệu CSV cho màn hình khách hàng nhé",
        "message": "Đã xong rồi nhé",
    },
    {
        "name": "plan-approved",
        "anchor": "Bên mình thống nhất chọn phương án B cho hợp đồng bảo trì",
        "message": "Cái đó bên anh duyệt chưa?",
    },
    {
        "name": "reviewer-replied",
        "anchor": "Chị Lan bên QA sẽ là người rà soát bản build này",
        "message": "Bạn ấy phản hồi chưa?",
    },
    {
        "name": "invoice-sent",
        "anchor": "Hoá đơn tháng trước bên kế toán sẽ gửi lại vào thứ sáu",
        "message": "Gửi chưa anh?",
    },
    {
        "name": "server-restarted",
        "anchor": "Server staging phải khởi động lại sau khi đổi biến môi trường",
        "message": "Khởi động lại chưa?",
    },
    {
        "name": "design-signed-off",
        "anchor": "Bản thiết kế màn hình thanh toán cần khách duyệt trước khi làm",
        "message": "Duyệt rồi phải không?",
    },
    {
        "name": "bug-assigned",
        "anchor": "Lỗi đăng nhập bằng Google giao cho bạn Nam xử lý trong sprint này",
        "message": "Cái lỗi đó fix xong chưa?",
    },
    {
        "name": "contract-deadline",
        "anchor": "Hợp đồng gia hạn phải ký xong trước ngày mùng 10 tháng sau",
        "message": "Kịp hạn không anh?",
    },
    {
        "name": "training-data",
        "anchor": "Dữ liệu huấn luyện đợt này lấy từ log tháng 6 và tháng 7",
        "message": "Lấy đủ chưa em?",
    },
]


def _parse_model(spec: str) -> tuple[str, str]:
    """Split a `provider:model` specification, model optional."""
    provider, _, model = spec.partition(":")
    return provider, model


# Gemini's free tier allows 100 embedding requests a minute, and one model's
# seeding needs 108. Paced rather than retried-on-failure as the first line of
# defence: `embed` reports every failure the same way, as None, so a script that
# only reacted after the fact could not tell a rate limit from a dead key.
HOSTED_GAP_SECONDS = 0.7
RATE_LIMIT_PAUSE_SECONDS = 45


async def _embed_paced(text: str) -> list[float]:
    """Embed one string, staying inside a hosted provider's per-minute quota.

    Local models are not paced — there is nobody to be polite to, and the sweep
    is slow enough already.

    Raises:
        SystemExit: when a second attempt, after a full quota window, also
            returns nothing. At that point it is not a rate limit.
    """
    if get_settings().embedding_provider != "local":
        await asyncio.sleep(HOSTED_GAP_SECONDS)

    vector = await embed(text)
    if vector is not None:
        return vector

    print(f"    [!] embed trả None, chờ {RATE_LIMIT_PAUSE_SECONDS}s rồi thử lại")
    await asyncio.sleep(RATE_LIMIT_PAUSE_SECONDS)
    vector = await embed(text)
    if vector is None:
        raise SystemExit(
            "The embedding provider returned nothing twice, a minute apart. The "
            "pause only helps a per-minute limit; a per-day quota, a wrong "
            "vector width or a dead key all look identical from here because "
            "`embed` reports every failure as None. Read the warning it logged."
        )
    return vector


async def _seed(session, scenario: dict) -> tuple[str, str, list[str], list[str]]:
    """Write one scenario and return its conversation, last message, and window.

    Timestamps are set a minute apart by hand. `created_at` defaults to the
    database's `now()`, which in PostgreSQL is when the *transaction* opened, so
    seeding in one transaction gives every row the same instant and the recent
    window falls through to its tiebreaker — a random UUID. An earlier version
    of this measurement did exactly that and reported a comparison in which the
    anchor was already inside the window it was meant to be outside.
    """
    suffix = uuid.uuid4().hex[:8]
    # Three accounts, because the transcript has three speakers and the recent
    # window is labelled from `sender_id`. Two would collapse two of them into
    # one alias and change what the prompt sees.
    speakers = {
        alias: User(email=f"sweep-{alias}-{suffix}@example.test", password_hash="x")
        for alias in ("U01", "U02", "U03")
    }
    session.add_all(list(speakers.values()))
    await session.flush()

    owner = speakers["U01"]
    conversation = Conversation(type="group", created_by=owner.id)
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=user.id)
            for user in speakers.values()
        ]
    )

    # The anchor and the message under test are both U01's; the filler carries
    # its own speaker label, which is stripped here because the label the prompt
    # shows is derived from the account, not stored in the text.
    lines = [f"U01: {scenario['anchor']}", *FILLER, f"U01: {scenario['message']}"]
    message_ids: list[str] = []
    texts: list[str] = []
    try:
        return await _fill(
            session, conversation, speakers, owner, lines, texts, message_ids, suffix
        )
    except BaseException:
        # The caller records the conversation id only once this function
        # returns, so a failure partway through would otherwise strand every row
        # written so far — which is how a quota running out mid-run left 27
        # accounts and 9 conversations in the development database.
        await session.rollback()
        await session.execute(
            delete(Conversation).where(Conversation.id == conversation.id)
        )
        await session.execute(
            delete(User).where(User.id.in_([user.id for user in speakers.values()]))
        )
        await session.commit()
        raise


async def _fill(
    session, conversation, speakers, owner, lines, texts, message_ids, suffix
) -> tuple[str, str, list[str], list[str]]:
    """Write the messages and their vectors. Split out so `_seed` can clean up."""
    started = datetime.now(UTC) - timedelta(minutes=len(lines) + 1)
    last_id = ""
    for index, line in enumerate(lines):
        alias, _, text = line.partition(": ")
        texts.append(text)
        message = Message(
            client_message_id=f"sweep-{suffix}-{index}",
            conversation_id=conversation.id,
            sender_id=speakers.get(alias, owner).id,
            original_text=text,
            created_at=started + timedelta(minutes=index),
        )
        session.add(message)
        await session.flush()
        last_id = message.id
        message_ids.append(message.id)

        vector = await _embed_paced(text)
        session.add(
            MessageEmbedding(
                message_id=message.id,
                conversation_id=conversation.id,
                embedding=vector,
            )
        )

    await session.commit()
    # The window the graph would have had anyway: the newest messages except the
    # one being translated, oldest first.
    window_size = get_settings().agent_context_size
    window = texts[-(window_size + 1) : -1]
    window_ids = message_ids[-(window_size + 1) : -1]
    return conversation.id, last_id, window, window_ids


async def _query_vector(
    strategy: str, session, *, message: str, window: list[str], message_id: str
) -> tuple[list[float] | None, float]:
    """Build the search vector for one strategy, and time what it cost.

    The `message` strategy reads the vector already stored for that message,
    which is what production does and why it costs nothing on the request path.
    The other two embed at query time, and the milliseconds are returned so the
    comparison can weigh them against NFR-01.
    """
    started = time.perf_counter()
    if strategy == "message":
        vector = await session.scalar(
            select(MessageEmbedding.embedding).where(
                MessageEmbedding.message_id == message_id
            )
        )
        return (list(vector) if vector is not None else None), 0.0

    if strategy == "message_plus_previous":
        text = "\n".join([*window[-1:], message])
    elif strategy == "message_plus_recent":
        text = "\n".join([*window, message])
    else:
        text = "\n".join(window)

    vector = await _embed_paced(text)
    return vector, (time.perf_counter() - started) * 1000


async def _retrieve(
    session,
    conversation_id: str,
    message_id: str,
    vector,
    exclude_ids: list[str],
):
    """Rank the conversation's other messages against a query vector.

    Same table, same filters and same cosine ordering as
    `DatabaseContextProvider._nearest_by_meaning`, with two deliberate
    differences, both so the measurement can see more than production does.

    The recent window is dropped from the results, as production does — without
    that, a query built from the window simply returns the window. But the whole
    remaining ranking is returned rather than the first `rag_top_k`. Production
    over-fetches by the window size and truncates, which means a line ranked
    last and a line ranked just outside the cut are reported identically as a
    miss. The first version of this sweep truncated the same way and returned
    zero for every widened strategy on every model — 81 identical results, which
    is what a measurement looks like when it cannot see the thing it is
    measuring. The rank is the finding; hit@k is derived from it afterwards.
    """
    rows = (
        await session.scalars(
            select(Message)
            .join(MessageEmbedding, MessageEmbedding.message_id == Message.id)
            .where(
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
                Message.original_text != "",
                Message.id != message_id,
                MessageEmbedding.embedding.is_not(None),
            )
            .order_by(MessageEmbedding.embedding.cosine_distance(vector))
        )
    ).all()
    excluded = set(exclude_ids)
    return [row.original_text for row in rows if row.id not in excluded]


async def _cleanup(factory, conversation_ids: list[str]) -> None:
    """Remove everything this run created."""
    async with factory() as session:
        for conversation_id in conversation_ids:
            user_ids = (
                await session.scalars(
                    select(ConversationMember.user_id).where(
                        ConversationMember.conversation_id == conversation_id
                    )
                )
            ).all()
            await session.execute(
                delete(Conversation).where(Conversation.id == conversation_id)
            )
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def _chance_baseline(candidates: float, top_k: int) -> tuple[float, float]:
    """What a retriever that ranked at random would score on this set.

    Without it a hit rate is unreadable. Six candidates and a cut at three means
    coin-flipping scores 50%, so a configuration reported at 67% has found
    something worth roughly one scenario in six — which is a very different
    claim from "it works two times in three".

    Returns:
        Expected hit@k and expected MRR. Expected MRR for a uniformly random
        rank over n candidates is the nth harmonic number divided by n.
    """
    n = max(int(round(candidates)), 1)
    hit = min(top_k, n) / n
    mrr = sum(1 / rank for rank in range(1, n + 1)) / n
    return hit, mrr


async def main() -> int:
    """Seed once per embedding model, then score every strategy against it."""
    parser = argparse.ArgumentParser(description="Quét model embedding × chiến lược truy vấn")
    parser.add_argument(
        "--models",
        nargs="*",
        default=DEFAULT_MODELS,
        help="Danh sách provider:model. Rỗng phần model = mặc định của provider.",
    )
    parser.add_argument("--no-write", action="store_true", help="Không lưu kết quả")
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    top_k = settings.rag_top_k

    print(
        f"{len(SCENARIOS)} kịch bản · cửa sổ gần nhất={settings.agent_context_size} "
        f"· rag_top_k={top_k}\n"
    )

    rows: list[dict] = []
    for spec in args.models:
        provider, model = _parse_model(spec)
        # Read at call time by `get_embedder`, so switching model mid-process
        # only needs the settings object updated.
        object.__setattr__(settings, "embedding_provider", provider)
        object.__setattr__(settings, "embedding_model", model)

        label = f"{provider}:{model or 'mặc định'}"
        print(f"=== {label}")
        conversation_ids: list[str] = []
        try:
            seeded = []
            embed_started = time.perf_counter()
            async with factory() as session:
                for scenario in SCENARIOS:
                    conversation_id, message_id, window, window_ids = await _seed(
                        session, scenario
                    )
                    conversation_ids.append(conversation_id)
                    seeded.append(
                        (scenario, conversation_id, message_id, window, window_ids)
                    )
            seed_ms = (time.perf_counter() - embed_started) * 1000
            per_message_ms = seed_ms / (len(SCENARIOS) * (len(FILLER) + 2))

            for strategy in STRATEGIES:
                scores, query_costs = [], []
                for scenario, conversation_id, message_id, window, window_ids in seeded:
                    async with factory() as session:
                        vector, cost_ms = await _query_vector(
                            strategy,
                            session,
                            message=scenario["message"],
                            window=window,
                            message_id=message_id,
                        )
                        if vector is None:
                            continue
                        ranked = await _retrieve(
                            session, conversation_id, message_id, vector, window_ids
                        )
                    scores.append(score_retrieval(ranked, [scenario["anchor"]]))
                    query_costs.append(cost_ms)

                if not scores:
                    continue
                hit_rate = sum(1 for s in scores if 0 < s.rank <= top_k) / len(scores)
                mrr = sum(s.reciprocal_rank for s in scores) / len(scores)
                ranks = [s.rank for s in scores if s.rank]
                row = {
                    "embedding": label,
                    "strategy": strategy,
                    "scenarios": len(scores),
                    "hit_rate": round(hit_rate, 3),
                    "mrr": round(mrr, 3),
                    # The rank of the decisive line among everything retrieval
                    # could have returned. This is the number that separates a
                    # strategy that nearly works from one that is pointing the
                    # wrong way entirely.
                    "mean_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
                    "candidates": round(
                        sum(s.returned for s in scores) / len(scores), 1
                    ),
                    "query_ms": round(sum(query_costs) / len(query_costs), 1),
                    "embed_ms_per_message": round(per_message_ms, 1),
                }
                chance_hit, chance_mrr = _chance_baseline(row["candidates"], top_k)
                row["chance_hit_rate"] = round(chance_hit, 3)
                row["chance_mrr"] = round(chance_mrr, 3)
                rows.append(row)
                print(
                    f"    {strategy:20} hit@{top_k}={hit_rate:.0%} "
                    f"MRR={mrr:.3f} "
                    f"hạng TB={row['mean_rank']}/{row['candidates']:.0f} "
                    f"· truy vấn +{row['query_ms']:.0f}ms "
                    f"· ngẫu nhiên: hit={chance_hit:.0%} MRR={chance_mrr:.3f}"
                )
        finally:
            await _cleanup(factory, conversation_ids)
        print()

    if not args.no_write and rows:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = RESULTS_DIR / f"sweep-{run_id}.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "agent_context_size": settings.agent_context_size,
                    "rag_top_k": top_k,
                    "scenarios": [s["name"] for s in SCENARIOS],
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Đã lưu: {path}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    from src.services.embeddings import preload_local_models

    preload_local_models()
    raise SystemExit(asyncio.run(main()))
