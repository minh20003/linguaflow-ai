"""Regression coverage for CI database cleanup behavior."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy.exc import DBAPIError

from tests import conftest as test_support


class _DriverError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(f"PostgreSQL error {sqlstate}")
        self.sqlstate = sqlstate


class _FakeConnection:
    def __init__(self, error: DBAPIError) -> None:
        self.error = error
        self.execute_count = 0

    async def execute(self, _statement: object) -> None:
        self.execute_count += 1
        if self.execute_count == 2:
            raise self.error


class _ConnectionContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeEngine:
    def __init__(self, error: DBAPIError) -> None:
        self.connection = _FakeConnection(error)
        self.disposed = False

    def connect(self) -> _ConnectionContext:
        return _ConnectionContext(self.connection)

    async def dispose(self) -> None:
        self.disposed = True


def _dbapi_error(sqlstate: str) -> DBAPIError:
    return DBAPIError(
        statement='DROP SCHEMA IF EXISTS "test_schema" CASCADE',
        params=None,
        orig=_DriverError(sqlstate),
        connection_invalidated=False,
    )


@pytest.mark.asyncio
async def test_cleanup_ignores_only_postgres_lock_timeout(monkeypatch, caplog) -> None:
    engine = _FakeEngine(_dbapi_error("55P03"))
    monkeypatch.setattr(test_support, "create_async_engine", lambda *_args, **_kwargs: engine)

    with caplog.at_level(logging.WARNING):
        await test_support._run_on_test_database('DROP SCHEMA IF EXISTS "test_schema" CASCADE')

    assert engine.disposed is True
    assert "background task is still holding a lock" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_reraises_other_database_errors(monkeypatch) -> None:
    error = _dbapi_error("42P01")
    engine = _FakeEngine(error)
    monkeypatch.setattr(test_support, "create_async_engine", lambda *_args, **_kwargs: engine)

    with pytest.raises(DBAPIError) as raised:
        await test_support._run_on_test_database('DROP SCHEMA IF EXISTS "test_schema" CASCADE')

    assert raised.value is error
    assert engine.disposed is True
