"""Apply RailOne migrations using RAILONE_DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

from railone_postgres.migrations import MigrationRunner
from railone_postgres.runtime import psycopg_connection_factory


def main() -> None:
    dsn = os.environ.get("RAILONE_DATABASE_URL", "")
    results = MigrationRunner(
        connection_factory=psycopg_connection_factory(dsn),
        migrations_directory=Path(__file__).resolve().parent / "migrations",
    ).apply_all()
    for result in results:
        state = "already applied" if result.already_applied else "applied"
        print(f"{result.version}: {state}")


if __name__ == "__main__":
    main()
