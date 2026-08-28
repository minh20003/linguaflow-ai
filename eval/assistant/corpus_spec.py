"""What the assistant corpus contains, declared as scenarios rather than as text.

The rule that makes this corpus trustworthy: **a label is a consequence of how the
data was built, never a judgement made afterwards.** Each `PlantedFact` below says
which messages carry an answer; the builder writes exactly those messages and
records the positions it wrote them at. Nothing re-reads the transcript to decide
what is relevant, so there is no model in the labelling loop and no circularity
between what retrieval finds and what the answer key says it should have found.

That also settles what the filler may be. It is generated — by a model, or from
the template pool when quota runs out — because realistic office chatter is what
makes retrieval hard in the way production is hard. It carries no labels, so a
generator having a bad day costs realism, never correctness.

Speaker identity follows the rule already learned on the translation golden set:
neutral ids (`U01`), never role labels. A corpus that says "Manager:" hands the
model the register for free, and production supplies no such thing.

Six query kinds, each aimed at one way retrieval fails:

| kind | the failure it exposes |
|---|---|
| `single_hop` | none — the floor. If this fails, nothing else is worth reading |
| `multi_hop` | one fact spread over several short messages, so no single message holds it |
| `long_message` | the answer buried mid-way through a 1500-character message |
| `temporal` | "what did we settle last week" — needs the clock, not just the meaning |
| `negative` | the answer is not in the conversation; the only correct move is to say so |
| `ambiguous` | under-specified on purpose; the correct move is to ask, not to guess |
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Five tiers, spanning what the assistant will actually meet. The point of the
# span is that chunking strategies do not separate at small sizes: with ten
# messages every strategy retrieves everything, and the measurement says nothing.
# They begin to diverge around 200 and disagree sharply by 2000.


@dataclass(frozen=True, slots=True)
class TierSpec:
    """One size of conversation to build."""

    name: str
    message_count: int
    # How many distinct subjects the filler rotates through. More subjects means
    # more near-misses — chatter that looks relevant to the query and is not,
    # which is what separates a good retriever from a lucky one.
    topics: int
    # Messages of 1200-2000 characters, planted so `token_window` has something
    # to cut and the other strategies have something to choke on.
    long_messages: int
    languages: tuple[str, ...]
    # Which query kinds this tier can support. XS has no room to place the two
    # halves of a multi-hop fact far enough apart for the distance to mean
    # anything, so claiming to measure it there would be dishonest.
    kinds: tuple[str, ...]


TIERS: tuple[TierSpec, ...] = (
    TierSpec(
        name="XS",
        message_count=10,
        topics=1,
        long_messages=0,
        languages=("vi",),
        kinds=("single_hop", "negative"),
    ),
    TierSpec(
        name="S",
        message_count=50,
        topics=2,
        long_messages=0,
        languages=("vi", "en"),
        # No `multi_hop`: every multi-part fact here is spread over more than
        # fifty messages, and squeezing one into this tier would produce a row
        # labelled multi_hop that any recent window answers.
        kinds=("single_hop", "negative", "ambiguous"),
    ),
    TierSpec(
        name="M",
        message_count=200,
        topics=4,
        long_messages=3,
        languages=("vi", "en"),
        kinds=("single_hop", "multi_hop", "long_message", "temporal", "negative", "ambiguous"),
    ),
    TierSpec(
        name="L",
        message_count=800,
        topics=6,
        long_messages=6,
        languages=("vi", "en", "ja"),
        kinds=("single_hop", "multi_hop", "long_message", "temporal", "negative", "ambiguous"),
    ),
    TierSpec(
        name="XL",
        message_count=2000,
        topics=8,
        long_messages=10,
        languages=("vi", "en", "ja"),
        kinds=("single_hop", "multi_hop", "long_message", "temporal", "negative", "ambiguous"),
    ),
)

TIERS_BY_NAME = {tier.name: tier for tier in TIERS}


@dataclass(frozen=True, slots=True)
class PlantedFact:
    """One thing the conversation says, and the question it answers.

    ``messages`` is written into the transcript verbatim. The builder records the
    index of each, and those indexes become the answer key — which is why the
    key cannot drift from the data even when the surrounding filler is
    regenerated.

    ``spread`` is what makes `multi_hop` a real test rather than a label. With a
    spread of 200, the parts of one fact are two hundred messages apart, so no
    recent-message window and no single chunk can contain them all; retrieval
    has to find each part on its own merits.
    """

    key: str
    kind: str
    question: str
    messages: tuple[str, ...]
    # What a correct answer must contain. Substrings, checked case-insensitively,
    # so a generated answer is graded on facts rather than on phrasing.
    answer_points: tuple[str, ...] = field(default_factory=tuple)
    spread: int = 0
    # Actions a correct extraction must produce from this fact, if any.
    expected_actions: tuple[dict[str, str], ...] = field(default_factory=tuple)


# --- The facts -------------------------------------------------------------
#
# Deliberately mundane and deliberately multilingual. A fact stated in Japanese
# and asked about in Vietnamese is the case this product exists for, and it is
# also the case a monolingual embedding quietly fails at while scoring well
# overall.

FACTS: tuple[PlantedFact, ...] = (
    PlantedFact(
        key="deadline-moved",
        kind="single_hop",
        question="Deadline cuối cùng của milestone thanh toán là ngày nào?",
        messages=("Chốt lại deadline milestone thanh toán là ngày 13 tháng 9, không phải 15.",),
        answer_points=("13",),
    ),
    PlantedFact(
        key="db-choice",
        kind="single_hop",
        question="Which database did we pick for the reporting service?",
        messages=("We are going with ClickHouse for the reporting service, not Postgres.",),
        answer_points=("clickhouse",),
    ),
    PlantedFact(
        key="release-owner",
        kind="multi_hop",
        question="Ai chịu trách nhiệm bản phát hành tháng 10 và vì sao đổi người?",
        messages=(
            "Bản phát hành tháng 10 vẫn để Quang phụ trách như mọi khi nhé.",
            "Quang báo là tuần đó anh ấy nghỉ phép cả tuần, không trực được.",
            "Vậy đổi sang Hà phụ trách bản phát hành tháng 10, Quang bàn giao trước khi nghỉ.",
        ),
        answer_points=("hà", "nghỉ phép"),
        spread=180,
    ),
    PlantedFact(
        key="invoice-split",
        kind="multi_hop",
        question="How much is the client actually invoiced this quarter, and why did it change?",
        messages=(
            "The draft invoice for this quarter came to 42,000 USD.",
            "Legal said the training days were quoted separately and must come off this invoice.",
            "Training was 7,000, so the invoice this quarter is 35,000 USD.",
        ),
        answer_points=("35,000", "training"),
        spread=140,
    ),
    PlantedFact(
        key="incident-cause",
        kind="multi_hop",
        question="根本原因は何でしたか、そして再発防止策は?",
        messages=(
            "昨夜の障害はキャッシュの設定ミスが原因でした。",
            "TTLが0になっていて、全リクエストがデータベースに直接届いていました。",
            "再発防止として、TTLの値をデプロイ前に検証するチェックを追加します。",
        ),
        answer_points=("ttl",),
        spread=120,
    ),
    PlantedFact(
        key="migration-plan",
        kind="long_message",
        question="Trong kế hoạch migration, bước nào phải làm trước khi tắt hệ thống cũ?",
        # The answer sits in the middle of a deliberately long message. This is
        # the case a one-message-per-chunk index dilutes into a single vector
        # describing fifty things at once.
        messages=(
            "Mình tổng hợp lại kế hoạch migration để mọi người cùng nắm. "
            "Giai đoạn một là dựng schema mới song song với schema cũ, không đụng gì tới dữ liệu đang chạy, "
            "dự kiến mất khoảng ba ngày và không cần downtime. "
            "Giai đoạn hai là bật cơ chế ghi kép, tức là mọi thao tác ghi sẽ vào cả hai schema cùng lúc, "
            "để dữ liệu mới luôn có mặt ở cả hai nơi trong khi vẫn đọc từ schema cũ. "
            "Giai đoạn này cần theo dõi kỹ độ trễ ghi vì chúng ta nhân đôi số lần ghi. "
            "Trước khi tắt hệ thống cũ thì bắt buộc phải chạy đối soát toàn bộ dữ liệu giữa hai schema và "
            "báo cáo tỉ lệ khớp đạt một trăm phần trăm, không có ngoại lệ nào được bỏ qua. "
            "Giai đoạn ba là chuyển đường đọc sang schema mới theo từng phần trăm lưu lượng, "
            "bắt đầu từ năm phần trăm rồi tăng dần nếu không có lỗi. "
            "Giai đoạn bốn là gỡ cơ chế ghi kép và dọn schema cũ, việc này để sau ít nhất hai tuần "
            "kể từ khi toàn bộ lưu lượng đọc đã chuyển sang, phòng khi phải quay lại. "
            "Về nhân sự thì mỗi giai đoạn cần một người trực chính và một người trực phụ, "
            "danh sách cụ thể mình sẽ gửi trong file riêng. "
            "Về công cụ, mình sẽ dựng một bảng theo dõi hiển thị số dòng ở mỗi schema theo từng bảng, "
            "cập nhật mỗi năm phút, để ai cũng nhìn được tiến độ mà không phải hỏi. "
            "Rủi ro lớn nhất mình thấy là khoảng thời gian ghi kép kéo dài hơn dự kiến, "
            "vì mỗi ngày trôi qua là một ngày chúng ta trả gấp đôi chi phí ghi mà chưa thu được lợi ích gì. "
            "Nếu sau mười ngày mà tỉ lệ khớp vẫn chưa đạt, mình đề nghị dừng lại và họp lại từ đầu "
            "thay vì cố đẩy tiếp theo lịch cũ. "
            "Cuối cùng, mọi thay đổi schema trong giai đoạn này đều phải đi qua Alembic như bình thường, "
            "không ai được sửa tay trên cơ sở dữ liệu dù chỉ một cột, "
            "vì đó là cách nhanh nhất để hai môi trường lệch nhau mà không ai biết.",
        ),
        answer_points=("đối soát", "một trăm phần trăm"),
    ),
    PlantedFact(
        key="onboarding-doc",
        kind="long_message",
        question="In the onboarding write-up, what must a new engineer do before their first deploy?",
        messages=(
            "Writing up the onboarding steps so we stop repeating them in DMs. "
            "Day one is accounts and access: SSO, the repository, the staging cluster, and the on-call rota, "
            "and please do all four on the same day because the access review runs weekly and a missed one "
            "costs you another week of waiting. "
            "Day two is the local environment, which is one command now, though the database container still "
            "needs Docker running inside WSL rather than Docker Desktop on this project. "
            "Day three onward is a starter ticket, something small and real rather than a toy. "
            "Before your first deploy you must pair with someone who has deployed before and walk the rollback "
            "procedure end to end, not read it, actually run it against staging and watch it come back. "
            "We added that rule after the March incident where a rollback was attempted for the first time "
            "under pressure and took forty minutes. "
            "After the first deploy you are on the rota like everyone else, "
            "and the expectation is that you ask early rather than quietly getting stuck. "
            "On the rota itself: the primary carries the pager and the secondary is there so the primary "
            "can sleep, which means the secondary is not optional and not decorative. "
            "Handover happens at ten in the morning with both people present, not over chat, "
            "because the things that matter are the ones nobody thought to write down. "
            "If you are paged for something you do not understand, escalate within fifteen minutes; "
            "we would far rather be woken for nothing than read about it in the morning. "
            "Documentation lives in the repository next to the code it describes, never in a wiki, "
            "for the simple reason that a wiki page has no reviewer and drifts within a month. "
            "Expenses, laptops and anything else administrative go through the operations channel "
            "rather than to individuals, so there is a record when someone is away.",
        ),
        answer_points=("rollback", "pair"),
    ),
    PlantedFact(
        key="last-week-decision",
        kind="temporal",
        question="Tuần trước chúng ta chốt gì về ngôn ngữ mặc định của giao diện?",
        messages=("Chốt: ngôn ngữ mặc định của giao diện để tiếng Việt, người dùng đổi được trong cài đặt.",),
        answer_points=("tiếng việt",),
    ),
    PlantedFact(
        key="qa-signoff",
        kind="temporal",
        question="When did QA sign off on the payment flow, and with what caveat?",
        messages=(
            "QA signed off on the payment flow today, with the caveat that refunds are still untested.",
        ),
        answer_points=("refund",),
    ),
    PlantedFact(
        key="standup-commitment",
        kind="single_hop",
        # Not "trong buổi standup". The transcript never mentions a standup, so
        # that wording smuggled a premise into the question — and the assistant
        # declining to answer it was *correct*, while the harness scored it as a
        # miss. The same defect as a context line carrying a role label, in
        # reverse: a question must not assert anything the corpus does not.
        question="Mình đã hứa gửi tài liệu gì, và hạn khi nào?",
        messages=("Mình sẽ gửi bản nháp báo cáo hiệu năng trước 5h chiều thứ Sáu.",),
        answer_points=("báo cáo hiệu năng", "thứ sáu"),
        expected_actions=(
            {
                "action_type": "task",
                "title": "gửi bản nháp báo cáo hiệu năng",
                "when": "friday 17:00",
            },
        ),
    ),
    PlantedFact(
        key="design-review-meeting",
        kind="single_hop",
        question="Buổi review thiết kế diễn ra khi nào?",
        messages=("Buổi review thiết kế chốt 10h sáng thứ Tư tuần sau, phòng họp lớn.",),
        answer_points=("10h", "thứ tư"),
        expected_actions=(
            {
                "action_type": "appointment",
                "title": "review thiết kế",
                "when": "wednesday 10:00",
            },
        ),
    ),
    # --- Negatives: the answer is genuinely absent -------------------------
    #
    # These plant nothing. A retriever will still return its best guesses,
    # because a vector index always returns *something* — the measurement is
    # whether generation refuses to answer from them. Systems that score well on
    # everything else routinely fail here, and it is the failure users notice,
    # because a confident invented answer is worse than no answer.
    PlantedFact(
        key="absent-budget",
        kind="negative",
        question="Ngân sách marketing quý tới được duyệt bao nhiêu?",
        messages=(),
    ),
    PlantedFact(
        key="absent-vendor",
        kind="negative",
        question="Which vendor did we choose for the security audit?",
        messages=(),
    ),
    PlantedFact(
        key="absent-headcount",
        kind="negative",
        question="来年の採用計画は何人ですか?",
        messages=(),
    ),
    # --- Ambiguous: the correct move is to ask ----------------------------
    PlantedFact(
        key="ambiguous-reschedule",
        kind="ambiguous",
        question="Dời cuộc họp sang hôm khác giúp mình.",
        messages=(
            "Sáng thứ Ba có họp kế hoạch, chiều thứ Ba có họp với khách hàng.",
        ),
        answer_points=("nào",),
    ),
    PlantedFact(
        key="ambiguous-remind",
        kind="ambiguous",
        question="Remind me about the report later.",
        messages=("There is a weekly report and a quarterly report in flight right now.",),
        answer_points=("which",),
    ),
)

FACTS_BY_KIND: dict[str, list[PlantedFact]] = {}
for _fact in FACTS:
    FACTS_BY_KIND.setdefault(_fact.kind, []).append(_fact)


def facts_for_tier(tier: TierSpec) -> list[PlantedFact]:
    """Which facts a tier can honestly host.

    A fact whose `spread` exceeds the tier's message count is dropped rather
    than squeezed in: planting a "two hundred messages apart" fact into a fifty
    message conversation produces a row labelled `multi_hop` that any recent
    window answers, which would report a difficulty the corpus does not contain.
    """
    return [
        fact
        for fact in FACTS
        if fact.kind in tier.kinds and fact.spread < tier.message_count
    ]
