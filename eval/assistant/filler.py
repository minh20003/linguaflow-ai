"""Realistic office chatter to bury the planted facts in.

Filler is what makes retrieval hard in the way production is hard. A conversation
of ten relevant messages is not a test; a conversation of two thousand messages
where nine hundred of them are *plausibly* about the same project is.

Two sources, in this order:

1. A model, when a key is configured. Prose it writes varies in a way a template
   pool cannot, which matters because a retriever can learn the shape of a
   template and score well on nothing.
2. The pool below, when there is no key or the quota is gone. Generated once and
   written to JSONL, so a corpus is built rarely and read often — a quota outage
   costs realism on the next build, never a broken measurement.

Filler carries **no labels**, which is what makes falling back safe. Nothing in
the answer key depends on a single word of it.

Mixed vi / en / ja deliberately, following `eval/rag_sweep.py`. A same-language
corpus lets an embedding model score by matching script and vocabulary — exactly
the shortcut that disappears in this product's real threads.
"""

from __future__ import annotations

import random

# Subjects the filler rotates through. Each is ordinary project talk about
# something *other* than the planted facts, which is harder and fairer than
# off-topic small talk: the near-misses are what separate a good retriever from
# a lucky one.
TOPICS: tuple[str, ...] = (
    "ci",
    "design",
    "support",
    "infra",
    "planning",
    "docs",
    "hiring",
    "tooling",
)

# Roughly twenty lines per topic per language would be unreadable here; the pool
# is a seed set that `_vary` recombines. Sentences are deliberately bland.
POOL: dict[str, dict[str, tuple[str, ...]]] = {
    "ci": {
        "vi": (
            "Pipeline CI sáng nay chạy chậm hơn thường lệ",
            "Mình vừa thêm bước cache cho dependency",
            "Test flaky ở phần upload lại xuất hiện",
            "Đã pin lại version của action checkout",
        ),
        "en": (
            "The CI queue backed up again this morning",
            "I split the test job into two shards",
            "That flaky upload test failed once more",
            "Build time is down to nine minutes now",
        ),
        "ja": (
            "CIのキャッシュを有効にしました",
            "テストが時々失敗する件、調査中です",
            "ビルド時間が短くなりました",
            "依存関係を更新しました",
        ),
    },
    "design": {
        "vi": (
            "Bản thiết kế mới cho màn hình danh sách đã lên Figma",
            "Mình nghĩ nên giữ nguyên bố cục hiện tại",
            "Màu nhấn hơi chìm trên nền sáng",
            "Đã cập nhật spacing theo hệ thống token",
        ),
        "en": (
            "New mockups for the list screen are up",
            "The accent colour reads too pale on light",
            "Spacing now follows the token scale",
            "Can we keep the current layout for now",
        ),
        "ja": (
            "デザインのレビューをお願いします",
            "レイアウトの変更は最小限にしたいです",
            "余白の調整をしました",
            "配色を少し暗くしました",
        ),
    },
    "support": {
        "vi": (
            "Khách hàng hỏi lại về thời gian phản hồi",
            "Có hai ticket mới về đăng nhập",
            "Mình đã trả lời ticket hôm qua rồi",
            "Bên hỗ trợ báo lượng ticket giảm",
        ),
        "en": (
            "Two new tickets about the login redirect",
            "The client asked about response times again",
            "I replied to yesterday's ticket already",
            "Ticket volume is down week over week",
        ),
        "ja": (
            "問い合わせが二件来ています",
            "昨日のチケットには返信済みです",
            "対応時間について質問がありました",
            "サポートの件数は減っています",
        ),
    },
    "infra": {
        "vi": (
            "Staging vừa được deploy lại",
            "Cache chưa được xoá sau lần deploy trước",
            "Dung lượng đĩa trên node hai đang cao",
            "Đã tăng số replica lên ba",
        ),
        "en": (
            "Staging has been redeployed",
            "Disk usage on node two is climbing",
            "I bumped the replica count to three",
            "The cache was not cleared after the deploy",
        ),
        "ja": (
            "ステージングを再デプロイしました",
            "ディスク使用量が増えています",
            "キャッシュの削除は手動で行いました",
            "レプリカ数を増やしました",
        ),
    },
    "planning": {
        "vi": (
            "Lịch sprint tuần sau mình sẽ gửi sau",
            "Việc export để sang phase sau",
            "Ưu tiên phần đăng nhập trước đã",
            "Mình cần thêm một ngày cho phần này",
        ),
        "en": (
            "I will send next sprint's plan later",
            "Export can wait for the next phase",
            "Login comes before everything else",
            "I need one more day on this piece",
        ),
        "ja": (
            "来週の予定は後で共有します",
            "エクスポートは次のフェーズにします",
            "ログインを優先しましょう",
            "もう一日ください",
        ),
    },
    "docs": {
        "vi": (
            "Mình đã cập nhật phần cài đặt trong README",
            "Tài liệu API còn thiếu ví dụ lỗi",
            "Đã thêm ghi chú về biến môi trường",
            "Phần hướng dẫn chạy local đã cũ",
        ),
        "en": (
            "I updated the setup section in the README",
            "The API docs are missing error examples",
            "Added a note about the environment variables",
            "The local setup guide is out of date",
        ),
        "ja": (
            "READMEを更新しました",
            "APIドキュメントに例を追加します",
            "環境変数の説明を書きました",
            "手順書が古くなっています",
        ),
    },
    "hiring": {
        "vi": (
            "Buổi phỏng vấn chiều nay dời sang 4h",
            "Mình đã gửi phản hồi cho ứng viên",
            "Còn hai hồ sơ cần đọc",
            "Vòng kỹ thuật diễn ra tuần sau",
        ),
        "en": (
            "This afternoon's interview moved to four",
            "I sent feedback on the candidate already",
            "Two more profiles left to read",
            "The technical round is next week",
        ),
        "ja": (
            "面接の時間が変更になりました",
            "候補者へのフィードバックを送りました",
            "書類がまだ二件残っています",
            "技術面接は来週です",
        ),
    },
    "tooling": {
        "vi": (
            "Đã bật formatter tự động khi commit",
            "Linter báo mấy lỗi import chưa dùng",
            "Mình chuyển sang dùng script chung",
            "Cấu hình editor đã được chia sẻ",
        ),
        "en": (
            "Enabled the formatter on commit",
            "The linter flagged some unused imports",
            "I switched to the shared script",
            "Editor config is in the repo now",
        ),
        "ja": (
            "フォーマッタを有効にしました",
            "未使用のインポートが指摘されました",
            "共通スクリプトに切り替えました",
            "エディタ設定を共有しました",
        ),
    },
}

# Appended to a pooled line to keep two thousand messages from repeating
# verbatim. Bland on purpose: a suffix carrying meaning would start competing
# with the planted facts for retrieval, and the corpus would stop measuring what
# it claims to.
_SUFFIXES: dict[str, tuple[str, ...]] = {
    "vi": ("nhé", "nha", "mọi người xem giúp", "cảm ơn", "để mình theo dõi tiếp", ""),
    "en": ("thanks", "let me know", "no rush", "for visibility", "will follow up", ""),
    "ja": ("よろしくお願いします", "ご確認ください", "共有まで", "以上です", ""),
}


def make_filler(
    count: int,
    *,
    topics: int,
    languages: tuple[str, ...],
    seed: int,
) -> list[tuple[str, str]]:
    """Build ``count`` filler lines as ``(language, text)`` pairs.

    Seeded, so rebuilding a tier without regenerating produces the identical
    corpus. That is not tidiness: a chunking sweep compares strategies over one
    corpus, and a corpus that shifts between runs turns every comparison into a
    comparison of two different datasets.

    Args:
        count: How many lines to produce.
        topics: How many subjects to rotate through, capped at what the pool has.
        languages: Which languages to draw from.
        seed: Random seed.
    """
    rng = random.Random(seed)
    chosen_topics = TOPICS[: max(1, min(topics, len(TOPICS)))]
    usable = [language for language in languages if language in _SUFFIXES] or ["en"]

    lines: list[tuple[str, str]] = []
    while len(lines) < count:
        topic = chosen_topics[len(lines) % len(chosen_topics)]
        language = usable[len(lines) % len(usable)]
        pool = POOL[topic].get(language) or POOL[topic]["en"]
        suffix = rng.choice(_SUFFIXES.get(language, ("",)))
        body = rng.choice(pool)
        lines.append((language, f"{body} {suffix}".strip()))
    return lines


def make_long_filler(
    count: int,
    *,
    topics: int,
    languages: tuple[str, ...],
    seed: int,
    min_chars: int = 1200,
) -> list[tuple[str, str]]:
    """Build ``count`` long, unlabelled messages of at least ``min_chars``.

    These carry no answers and are never queried. They exist so the corpus poses
    the problem at scale that the two labelled `long_message` facts pose once: a
    conversation where several messages are far longer than a chunk budget, so
    `token_window` has real work to do and the strategies that cannot split a
    message are handicapped everywhere rather than in two places.

    Unlabelled on purpose. Adding more labelled long messages would measure the
    same thing twice; adding unlabelled ones makes the haystack the right shape.
    """
    rng = random.Random(seed + 1)
    chosen_topics = TOPICS[: max(1, min(topics, len(TOPICS)))]
    usable = [language for language in languages if language in _SUFFIXES] or ["en"]

    messages: list[tuple[str, str]] = []
    for position in range(count):
        language = usable[position % len(usable)]
        # Drawn from several topics, because a long message in a real thread is
        # someone writing up a meeting, not one sentence repeated.
        sentences: list[str] = []
        while sum(len(sentence) for sentence in sentences) < min_chars:
            topic = rng.choice(chosen_topics)
            pool = POOL[topic].get(language) or POOL[topic]["en"]
            sentences.append(rng.choice(pool))
        messages.append((language, ". ".join(sentences) + "."))
    return messages
