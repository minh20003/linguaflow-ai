"""PostgreSQL-only proof that concurrent outbox claims skip locked rows."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_postgres_for_update_skip_locked_claims_a_different_row() -> None:
    database_url = os.getenv("TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("TEST_POSTGRES_URL is required for the PostgreSQL integration test")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    table = f"outbox_lock_test_{uuid4().hex}"
    try:
        async with engine.begin() as setup:
            await setup.execute(
                text(
                    f"CREATE TABLE {table} ("
                    "id INTEGER PRIMARY KEY, status TEXT NOT NULL, available_at TIMESTAMPTZ NOT NULL)"
                )
            )
            await setup.execute(
                text(
                    f"INSERT INTO {table} (id, status, available_at) VALUES "
                    "(1, 'pending', NOW()), (2, 'pending', NOW())"
                )
            )

        first_connection = await engine.connect()
        first_transaction = await first_connection.begin()
        second_connection = await engine.connect()
        second_transaction = await second_connection.begin()
        try:
            first_id = await first_connection.scalar(
                text(
                    f"SELECT id FROM {table} WHERE status = 'pending' "
                    "ORDER BY id LIMIT 1 FOR UPDATE"
                )
            )
            second_id = await second_connection.scalar(
                text(
                    f"SELECT id FROM {table} WHERE status = 'pending' "
                    "ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            )
            assert first_id == 1
            assert second_id == 2
        finally:
            await second_transaction.rollback()
            await second_connection.close()
            await first_transaction.rollback()
            await first_connection.close()
    finally:
        async with engine.begin() as cleanup:
            await cleanup.execute(text(f"DROP TABLE IF EXISTS {table}"))
        await engine.dispose()
