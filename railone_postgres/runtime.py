"""Small PostgreSQL runtime boundary used by RailOne durable repositories.

The domain packages depend on repository protocols, not psycopg.  This module
keeps the driver at the composition root and makes transaction ownership
explicit: every repository operation receives a fresh connection and either
commits completely or rolls back completely.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Protocol


class Cursor(Protocol):
    rowcount: int

    def execute(self, query: str, params: Sequence[object] = ()) -> "Cursor": ...
    def fetchone(self) -> Mapping[str, Any] | None: ...
    def fetchall(self) -> list[Mapping[str, Any]]: ...
    def __enter__(self) -> "Cursor": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


ConnectionFactory = Callable[[], Connection]


class PostgresDatabase:
    """Owns short-lived transactions and never exposes a global connection."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        connection = self._connection_factory()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def psycopg_connection_factory(dsn: str) -> ConnectionFactory:
    """Return a psycopg connection factory without importing it at module load.

    Production installs use ``psycopg[binary]`` or an organization-approved
    psycopg build.  Unit tests can inject a DB-API compatible factory without a
    running database.
    """

    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("PostgreSQL DSN is required")
    normalized = dsn.strip()

    def connect() -> Connection:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "PostgreSQL runtime requires the optional 'postgres' dependency"
            ) from exc
        return psycopg.connect(normalized, row_factory=dict_row)

    return connect
