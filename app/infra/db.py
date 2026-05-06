"""Postgres session helper for LangGraph checkpoints.

I/O glue, excluded from coverage and mypy strict per Constitution TD-2.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.infra.settings import get_settings


@contextmanager
def pg_connection() -> Iterator[psycopg.Connection]:
    """Yield a Postgres connection using the configured DSN.

    The connection is closed on context exit. LangGraph's Postgres checkpoint
    saver manages its own connection pool; this helper is for ad-hoc ops
    (replays, healthchecks, schema creation).
    """
    settings = get_settings()
    conn = psycopg.connect(settings.postgres_dsn)
    try:
        yield conn
    finally:
        conn.close()
