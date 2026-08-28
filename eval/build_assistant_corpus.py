"""Build the Assistant Agent's evaluation corpus.

    python eval/build_assistant_corpus.py --tier XS --dry-run
    python eval/build_assistant_corpus.py --tier XS,S,M,L,XL
    python eval/build_assistant_corpus.py --seed-db --tier M
    python eval/build_assistant_corpus.py --cleanup

Writes one JSONL file per tier under `eval/assistant/corpus/`, each holding a
whole conversation and the queries asked of it. Those files are **committed**, so
every measurement runs against identical data — a corpus regenerated between two
runs turns a comparison of strategies into a comparison of datasets.

The answer key is a by-product of construction. `corpus_spec.FACTS` says which
messages carry which answer; this script writes exactly those messages and
records the indexes it wrote them at. Nothing re-reads the transcript afterwards
to decide what was relevant, so no model is in the labelling loop.

`--seed-db` loads a built corpus into PostgreSQL as real users, conversations and
messages, which is what the chunk sweep measures over. Seeding is separate from
building for a plain reason: building is slow and rare, seeding is fast and
happens once per sweep.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assistant.corpus_spec import (  # noqa: E402
    TIERS,
    TIERS_BY_NAME,
    PlantedFact,
    TierSpec,
    facts_for_tier,
)
from assistant.filler import make_filler, make_long_filler  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import configure_logging, get_settings  # noqa: E402
from src.database.models import (  # noqa: E402
    AssistantChunk,
    Conversation,
    ConversationMember,
    Message,
    User,
)

CORPUS_DIR = Path(__file__).parent / "assistant" / "corpus"

# Three speakers, as in `eval/rag_sweep.py`. Neutral ids rather than names or
# roles: production supplies no role label, and a corpus that leaks one hands
# the model register information it will not have in the real thing.
SPEAKERS = ("U01", "U02", "U03")

# Marks a corpus account so `--cleanup` can find every row it wrote without
# guessing from a timestamp.
EMAIL_DOMAIN = "assistant-corpus.test"

# One message a minute. Real enough for `turn_window` gaps and `temporal`
# queries to mean something, and regular enough that a rebuild produces the
# identical timeline.
MESSAGE_INTERVAL_SECONDS = 60


@dataclass
class CorpusMessage:
    """One line of the built conversation."""

    index: int
    speaker: str
    language: str
    text: str
    offset_seconds: int
    # Which planted fact this line carries, if any. Empty for filler.
    fact_key: str = ""


@dataclass
class CorpusQuery:
    """One question, and the messages that answer it."""

    key: str
    kind: str
    question: str
    # Indexes into `CorpusDocument.messages`. Empty for `negative` queries, which
    # is the whole point of them: the correct retrieval is nothing, and the
    # correct answer is a refusal.
    relevant_indexes: list[int] = field(default_factory=list)
    answer_points: list[str] = field(default_factory=list)
    expected_actions: list[dict] = field(default_factory=list)


@dataclass
class CorpusDocument:
    """A whole tier: one conversation plus everything asked of it."""

    tier: str
    seed: int
    built_at: str
    messages: list[CorpusMessage]
    queries: list[CorpusQuery]


def _placements(tier: TierSpec, facts: list[PlantedFact]) -> dict[str, list[int]]:
    """Decide where each fact's messages go, before any text is written.

    Placement first, text second, because the distances are the difficulty. A
    `multi_hop` fact whose parts land next to each other is a `single_hop` fact
    wearing a different label, and the run would report a strength the retriever
    does not have.

    Facts are spaced across the conversation rather than clustered, so no single
    window of any size covers several of them at once.
    """
    total = tier.message_count
    placements: dict[str, list[int]] = {}
    planted = [fact for fact in facts if fact.messages]
    if not planted:
        return placements

    # Leave the first and last tenth clear. A fact at index 0 is found by any
    # retriever that reads from the start, and one at the end is inside every
    # recent-message window — both would flatter the result.
    lower, upper = total // 10, total - total // 10
    span = max(upper - lower, len(planted))
    step = span // len(planted)

    for position, fact in enumerate(planted):
        anchor = lower + position * step
        if len(fact.messages) == 1:
            placements[fact.key] = [min(anchor, total - 1)]
            continue
        # Spread the parts of a multi-part fact, capped so they stay inside the
        # conversation even when `spread` is generous for this tier.
        gap = max(1, min(fact.spread, (total - anchor - 1) // max(len(fact.messages) - 1, 1)))
        placements[fact.key] = [
            min(anchor + offset * gap, total - 1) for offset in range(len(fact.messages))
        ]
    return placements


def build_tier(tier: TierSpec, *, seed: int = 217) -> CorpusDocument:
    """Assemble one tier's conversation and answer key."""
    facts = facts_for_tier(tier)
    placements = _placements(tier, facts)

    # Reserve the slots the facts own, then fill everything else.
    taken: dict[int, tuple[PlantedFact, int]] = {}
    for fact in facts:
        for part, index in enumerate(placements.get(fact.key, [])):
            while index in taken and index < tier.message_count - 1:
                index += 1
            taken[index] = (fact, part)

    filler = make_filler(
        tier.message_count,
        topics=tier.topics,
        languages=tier.languages,
        seed=seed,
    )

    # Unlabelled long messages, scattered through the free slots. They make the
    # haystack the right shape: a conversation where several messages are far
    # longer than any chunk budget, so a strategy that cannot split a message is
    # handicapped throughout rather than at the two labelled long_message facts.
    long_slots: dict[int, tuple[str, str]] = {}
    if tier.long_messages:
        free = [index for index in range(tier.message_count) if index not in taken]
        stride = max(1, len(free) // tier.long_messages)
        chosen = free[:: stride][: tier.long_messages]
        for slot, body in zip(
            chosen,
            make_long_filler(
                len(chosen),
                topics=tier.topics,
                languages=tier.languages,
                seed=seed,
            ),
            strict=False,
        ):
            long_slots[slot] = body

    messages: list[CorpusMessage] = []
    for index in range(tier.message_count):
        if index in taken:
            fact, part = taken[index]
            text = fact.messages[part]
            # A planted fact keeps its own language, which is the point of
            # writing some of them in Japanese: a Vietnamese question about a
            # Japanese fact is the case this product exists for.
            language = "vi"
            if any(ord(char) > 0x3000 for char in text):
                language = "ja"
            elif text.isascii():
                language = "en"
            messages.append(
                CorpusMessage(
                    index=index,
                    speaker=SPEAKERS[index % len(SPEAKERS)],
                    language=language,
                    text=text,
                    offset_seconds=index * MESSAGE_INTERVAL_SECONDS,
                    fact_key=fact.key,
                )
            )
            continue

        language, text = long_slots.get(index) or filler[index]
        messages.append(
            CorpusMessage(
                index=index,
                speaker=SPEAKERS[index % len(SPEAKERS)],
                language=language,
                text=text,
                offset_seconds=index * MESSAGE_INTERVAL_SECONDS,
            )
        )

    by_fact: dict[str, list[int]] = {}
    for message in messages:
        if message.fact_key:
            by_fact.setdefault(message.fact_key, []).append(message.index)

    queries = [
        CorpusQuery(
            key=fact.key,
            kind=fact.kind,
            question=fact.question,
            relevant_indexes=by_fact.get(fact.key, []),
            answer_points=list(fact.answer_points),
            expected_actions=[dict(action) for action in fact.expected_actions],
        )
        for fact in facts
    ]

    return CorpusDocument(
        tier=tier.name,
        seed=seed,
        built_at=datetime.now(UTC).isoformat(),
        messages=messages,
        queries=queries,
    )


def validate(document: CorpusDocument) -> list[str]:
    """Check the built corpus against what it claims to be.

    Run before writing, because a corpus that is wrong in one of these ways
    produces numbers that look entirely reasonable. A `multi_hop` query whose
    parts landed adjacent reports high recall and has measured nothing; a
    `negative` query that accidentally has an answer marks a correct refusal as
    a failure.
    """
    problems: list[str] = []
    for query in document.queries:
        if query.kind == "negative":
            if query.relevant_indexes:
                problems.append(f"{query.key}: a negative query must plant nothing")
            continue
        if not query.relevant_indexes:
            problems.append(f"{query.key}: nothing was planted for a non-negative query")
            continue
        if query.kind == "multi_hop":
            if len(query.relevant_indexes) < 2:
                problems.append(f"{query.key}: multi_hop needs at least two messages")
            elif max(query.relevant_indexes) - min(query.relevant_indexes) < 20:
                problems.append(
                    f"{query.key}: multi_hop parts are {max(query.relevant_indexes) - min(query.relevant_indexes)} "
                    "apart, close enough that one window covers them"
                )
        if query.kind == "long_message":
            body = document.messages[query.relevant_indexes[0]].text
            if len(body) < 1000:
                problems.append(
                    f"{query.key}: long_message body is only {len(body)} characters"
                )
    return problems


def write(document: CorpusDocument) -> Path:
    """Write one tier as JSONL: a header line, then one line per message."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    path = CORPUS_DIR / f"{document.tier}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        header = {
            "type": "header",
            "tier": document.tier,
            "seed": document.seed,
            "built_at": document.built_at,
            "message_count": len(document.messages),
            "queries": [asdict(query) for query in document.queries],
        }
        handle.write(json.dumps(header, ensure_ascii=False) + "\n")
        for message in document.messages:
            handle.write(
                json.dumps({"type": "message", **asdict(message)}, ensure_ascii=False)
                + "\n"
            )
    return path


def load(tier: str) -> CorpusDocument:
    """Read a built tier back.

    Raises:
        FileNotFoundError: the tier has not been built yet.
    """
    path = CORPUS_DIR / f"{tier}.jsonl"
    with path.open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        messages = [
            CorpusMessage(
                **{key: value for key, value in json.loads(line).items() if key != "type"}
            )
            for line in handle
            if line.strip()
        ]
    return CorpusDocument(
        tier=header["tier"],
        seed=header["seed"],
        built_at=header["built_at"],
        messages=messages,
        queries=[CorpusQuery(**query) for query in header["queries"]],
    )


# --- Seeding ---------------------------------------------------------------


def _session_maker():
    """An engine of this script's own, as `eval/rag_sweep.py` does.

    Not the application's: this runs outside a request and must not inherit a
    pool sized for one.
    """
    engine = create_async_engine(get_settings().database_url, echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def seed_tier(document: CorpusDocument) -> str:
    """Write one built tier into PostgreSQL, returning the conversation id.

    Timestamps are set explicitly rather than left to `now()`. In PostgreSQL
    `now()` is when the *transaction* opened, so seeding in one transaction gives
    every row the same instant — and every ordering then falls through to its
    tiebreaker on a random uuid. An earlier measurement in this repository did
    exactly that and reported a comparison in which the anchor was already inside
    the window it was meant to be outside.
    """
    engine, session_maker = _session_maker()
    suffix = uuid.uuid4().hex[:8]
    try:
        async with session_maker() as session:
            users = {
                alias: User(
                    email=f"{alias.lower()}-{suffix}@{EMAIL_DOMAIN}",
                    password_hash="x",
                    display_name=alias,
                )
                for alias in SPEAKERS
            }
            session.add_all(list(users.values()))
            await session.flush()

            owner = users[SPEAKERS[0]]
            conversation = Conversation(
                type="group",
                created_by=owner.id,
                title=f"corpus-{document.tier}-{suffix}",
            )
            session.add(conversation)
            await session.flush()
            session.add_all(
                [
                    ConversationMember(
                        conversation_id=conversation.id, user_id=user.id
                    )
                    for user in users.values()
                ]
            )

            start = datetime.now(UTC) - timedelta(
                seconds=len(document.messages) * MESSAGE_INTERVAL_SECONDS
            )
            session.add_all(
                [
                    Message(
                        conversation_id=conversation.id,
                        client_message_id=f"corpus-{suffix}-{message.index}",
                        sender_id=users[message.speaker].id,
                        original_text=message.text,
                        source_language=message.language,
                        created_at=start + timedelta(seconds=message.offset_seconds),
                    )
                    for message in document.messages
                ]
            )
            await session.commit()
            return conversation.id
    finally:
        await engine.dispose()


async def cleanup() -> tuple[int, int]:
    """Remove every conversation and account this script has ever seeded.

    Identified by the marker domain rather than by age. A run that dies partway
    — a quota running out is the usual way — leaves rows behind, and an earlier
    version of the sweep script in this repository left 27 accounts and 9
    conversations in the development database exactly that way.
    """
    engine, session_maker = _session_maker()
    try:
        async with session_maker() as session:
            users = list(
                (
                    await session.scalars(
                        select(User).where(User.email.like(f"%@{EMAIL_DOMAIN}"))
                    )
                ).all()
            )
            if not users:
                return 0, 0
            user_ids = [user.id for user in users]

            conversations = list(
                (
                    await session.scalars(
                        select(Conversation.id).where(
                            Conversation.created_by.in_(user_ids)
                        )
                    )
                ).all()
            )
            if conversations:
                # Chunks cascade from conversations, but deleting them first
                # keeps the cascade small enough to stay inside one statement.
                await session.execute(
                    delete(AssistantChunk).where(
                        AssistantChunk.conversation_id.in_(conversations)
                    )
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id.in_(conversations))
                )
            await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.commit()
            return len(conversations), len(user_ids)
    finally:
        await engine.dispose()


# --- CLI -------------------------------------------------------------------


def _describe(document: CorpusDocument) -> str:
    by_kind: dict[str, int] = {}
    for query in document.queries:
        by_kind[query.kind] = by_kind.get(query.kind, 0) + 1
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(by_kind.items()))
    longest = max((len(message.text) for message in document.messages), default=0)
    return (
        f"{document.tier:3} {len(document.messages):5} tin · "
        f"{len(document.queries):2} câu hỏi · {kinds} · tin dài nhất {longest} ký tự"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier",
        default="XS,S,M,L,XL",
        help="Các bậc cần dựng, phân tách bằng dấu phẩy (mặc định: tất cả)",
    )
    parser.add_argument("--seed", type=int, default=217, help="Seed ngẫu nhiên")
    parser.add_argument(
        "--dry-run", action="store_true", help="Dựng và kiểm, không ghi tệp"
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Nạp corpus đã dựng vào PostgreSQL và in ra conversation_id",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Xoá mọi hội thoại và tài khoản do script này tạo, rồi thoát",
    )
    args = parser.parse_args()

    configure_logging()

    if args.cleanup:
        conversations, users = await cleanup()
        print(f"Đã xoá {conversations} hội thoại và {users} tài khoản corpus.")
        return 0

    names = [name.strip().upper() for name in args.tier.split(",") if name.strip()]
    unknown = [name for name in names if name not in TIERS_BY_NAME]
    if unknown:
        print(
            f"Bậc không hợp lệ: {', '.join(unknown)}. "
            f"Hợp lệ: {', '.join(tier.name for tier in TIERS)}",
            file=sys.stderr,
        )
        return 2

    failed = False
    for name in names:
        document = build_tier(TIERS_BY_NAME[name], seed=args.seed)
        problems = validate(document)

        print(_describe(document))
        for problem in problems:
            print(f"    ⚠️  {problem}")
        if problems:
            # A corpus that fails validation is not written. Numbers from it
            # would look reasonable and mean nothing, which is worse than having
            # no numbers.
            failed = True
            continue

        if not args.dry_run:
            print(f"    → {write(document)}")

        if args.seed_db:
            conversation_id = await seed_tier(document)
            print(f"    → conversation_id={conversation_id}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
