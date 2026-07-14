"""Checksum-locked PostgreSQL migration runner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .runtime import ConnectionFactory


_LOCK_ID = 7_410_007


class MigrationChecksumMismatchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AppliedMigration:
    version: str
    migration_sha256: str
    already_applied: bool


class MigrationRunner:
    def __init__(
        self, *, connection_factory: ConnectionFactory, migrations_directory: Path
    ) -> None:
        self._connection_factory = connection_factory
        self._directory = migrations_directory

    def apply_all(self) -> tuple[AppliedMigration, ...]:
        files = sorted(self._directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
        if not files:
            raise RuntimeError("no RailOne migrations were found")
        connection = self._connection_factory()
        results: list[AppliedMigration] = []
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
                cursor.execute("CREATE SCHEMA IF NOT EXISTS railone")
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS railone.schema_migrations (
                       version text PRIMARY KEY,
                       migration_sha256 char(64) NOT NULL,
                       applied_at timestamptz NOT NULL DEFAULT now())"""
                )
                connection.commit()
                for path in files:
                    results.append(self._apply(cursor, connection, path))
                cursor.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
                connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return tuple(results)

    @staticmethod
    def _apply(cursor, connection, path: Path) -> AppliedMigration:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        version = path.name.split("_", 1)[0]
        cursor.execute(
            "SELECT migration_sha256 FROM railone.schema_migrations WHERE version=%s",
            (version,),
        )
        existing = cursor.fetchone()
        if existing is not None:
            if existing["migration_sha256"] != digest:
                raise MigrationChecksumMismatchError(
                    f"applied migration {version} has changed"
                )
            return AppliedMigration(version, digest, True)
        body = _transaction_body(raw.decode("utf-8"))
        try:
            cursor.execute(body)
            cursor.execute(
                """INSERT INTO railone.schema_migrations
                   (version, migration_sha256) VALUES (%s,%s)""",
                (version, digest),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return AppliedMigration(version, digest, False)


def _transaction_body(sql: str) -> str:
    lines = sql.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[0].strip().upper() == "BEGIN;":
        lines.pop(0)
    if lines and lines[-1].strip().upper() == "COMMIT;":
        lines.pop()
    return "\n".join(lines).strip()
