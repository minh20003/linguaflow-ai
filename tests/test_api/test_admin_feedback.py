"""Tests for the administrator's view of reader feedback (F-05).

Two things are guarded. The gate, because `users.role == "admin"` is the whole
authorization model and a missing dependency looks like working code. And the
boundary: an administrator may see counts and the anonymised fragment prepared
at edit time, and nothing else — a correction whose author withheld consent
must be countable but never readable.

Fixtures live in this file rather than tests/conftest.py, which is shared
across all feature areas.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from src.database.models import CorrectionLog, Feedback, Message, TranslationResult


def response_text(body: dict) -> str:
    """The whole response as one string, for absence assertions."""
    return json.dumps(body, ensure_ascii=False)


async def _translation(test_db, conversation_id: str, sender_id: str) -> str:
    """Persist one message with one translation and return the translation id."""
    message = Message(
        client_message_id=f"fb-{sender_id[:8]}-{datetime.now(UTC).timestamp()}",
        conversation_id=conversation_id,
        sender_id=sender_id,
        original_text="Deploy xong chưa anh?",
        source_language="vi",
        created_at=datetime.now(UTC),
    )
    test_db.add(message)
    await test_db.commit()

    translation = TranslationResult(
        message_id=message.id,
        target_language="en",
        translated_text="Is the deploy done?",
        model="mistral-small-latest",
        latency_ms=640,
        is_fallback=False,
    )
    test_db.add(translation)
    await test_db.commit()
    return translation.id


def _correction(user_id: str, *, consent: bool, phrase: str, minutes: int = 0):
    """One row of the miner's evidence, consented or not."""
    return CorrectionLog(
        source_phrase=phrase,
        corrected_target="môi trường staging",
        source_language="en",
        target_language="vi",
        domain="engineering",
        audience="internal",
        user_id=user_id,
        consent_to_share=consent,
        anonymized_snippet=f"… {phrase} …",
        observed_at=datetime.now(UTC) - timedelta(minutes=minutes),
    )


@pytest.mark.asyncio
async def test_a_member_cannot_read_the_feedback_overview(client, test_user_headers):
    """The gate is one string comparison per endpoint, so each one needs its own."""
    response = await client.get("/api/v1/admin/feedback", headers=test_user_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_votes_are_tallied_into_up_down_and_neutral(
    client, test_db, test_admin_headers, test_user, test_user_two, conversation_factory
):
    """The interface sends 5 and 1; anything else has to land somewhere visible
    rather than being dropped on the way to the screen."""
    conversation = await conversation_factory(test_user, [test_user, test_user_two])
    first = await _translation(test_db, conversation.id, test_user_two.id)
    second = await _translation(test_db, conversation.id, test_user_two.id)

    test_db.add(Feedback(translation_id=first, user_id=test_user.id, rating=5))
    test_db.add(Feedback(translation_id=second, user_id=test_user.id, rating=1))
    test_db.add(Feedback(translation_id=first, user_id=test_user_two.id, rating=3))
    await test_db.commit()

    response = await client.get("/api/v1/admin/feedback", headers=test_admin_headers)

    assert response.status_code == 200
    votes = response.json()["votes"]
    assert (votes["up"], votes["down"], votes["neutral"]) == (1, 1, 1)
    assert votes["total"] == 3
    assert votes["up_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert votes["ratings"] == {"5": 1, "3": 1, "1": 1}


@pytest.mark.asyncio
async def test_a_correction_without_consent_is_counted_but_never_shown(
    client, test_db, test_admin_headers, test_user
):
    """Consent decides whether the wording may be read, not whether the row
    exists. Counting the withheld ones is what makes it visible that they are
    being left out rather than silently missing."""
    test_db.add(_correction(test_user.id, consent=True, phrase="staging environment"))
    test_db.add(_correction(test_user.id, consent=False, phrase="secret wording"))
    await test_db.commit()

    body = (
        await client.get("/api/v1/admin/feedback", headers=test_admin_headers)
    ).json()

    assert body["shared_total"] == 1
    assert body["withheld_total"] == 1
    phrases = [row["source_phrase"] for row in body["shared_corrections"]]
    assert phrases == ["staging environment"]
    assert "secret wording" not in response_text(body)


@pytest.mark.asyncio
async def test_a_shared_correction_carries_no_author_or_conversation(
    client, test_db, test_admin_headers, test_user
):
    """The DTO having nowhere to put them is what keeps the rule true; this
    test is what notices when a column is added back."""
    test_db.add(_correction(test_user.id, consent=True, phrase="staging environment"))
    await test_db.commit()

    body = (
        await client.get("/api/v1/admin/feedback", headers=test_admin_headers)
    ).json()

    row = body["shared_corrections"][0]
    assert set(row) == {
        "source_phrase",
        "corrected_target",
        "source_language",
        "target_language",
        "domain",
        "audience",
        "anonymized_snippet",
        "observed_at",
    }
    assert test_user.id not in response_text(body)


@pytest.mark.asyncio
async def test_shared_corrections_are_newest_first(
    client, test_db, test_admin_headers, test_user
):
    """A term the team started arguing about today is worth more attention than
    one from six weeks ago, the same way the proposal queue is ordered."""
    test_db.add(_correction(test_user.id, consent=True, phrase="older", minutes=90))
    test_db.add(_correction(test_user.id, consent=True, phrase="newer", minutes=1))
    await test_db.commit()

    body = (
        await client.get("/api/v1/admin/feedback", headers=test_admin_headers)
    ).json()

    assert [row["source_phrase"] for row in body["shared_corrections"]] == [
        "newer",
        "older",
    ]


@pytest.mark.asyncio
async def test_an_empty_system_reports_zeroes_rather_than_failing(
    client, test_admin_headers
):
    """The screen is opened on day one, before anybody has voted on anything."""
    body = (
        await client.get("/api/v1/admin/feedback", headers=test_admin_headers)
    ).json()

    assert body["votes"]["total"] == 0
    assert body["votes"]["up_rate"] == 0.0
    assert body["shared_corrections"] == []
