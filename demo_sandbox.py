"""Run a synthetic institutional transaction on an explicitly disposable PostgreSQL DB."""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("accepted", "timeout", "crash"), default="accepted")
    parser.add_argument(
        "--reset-disposable-db", action="store_true",
        help="Drop and rebuild railone and railone_bank schemas before seeding the demo.",
    )
    args = parser.parse_args()
    if not args.reset_disposable_db:
        parser.error("--reset-disposable-db is required; this demo rebuilds both RailOne schemas")
    if not os.environ.get("RAILONE_TEST_DATABASE_URL"):
        parser.error("set RAILONE_TEST_DATABASE_URL to your disposable PostgreSQL server")
    os.environ["RAILONE_ALLOW_TEST_SCHEMA_RESET"] = "1"
    os.environ["RAILONE_REQUIRE_LIVE_POSTGRES"] = "1"
    # Import after configuring the existing integration harness.
    from tests.test_postgres_live import LivePostgresRuntimeTests
    from tests.institutional_live_support import exercise_institutional_dispatch
    from railone_postgres import PostgresDatabase

    print(f"RailOne institutional sandbox demo — {args.scenario}", flush=True)
    print("Synthetic participants, keys, and adapter. Rebuilding disposable schemas.", flush=True)
    test = LivePostgresRuntimeTests(
        "test_institutional_dispatch_reserves_before_adapter_and_blocks_replay"
    )
    try:
        LivePostgresRuntimeTests.setUpClass()
        exercise_institutional_dispatch(
            test, PostgresDatabase(test.factory), scenario=args.scenario,
            report=lambda message: print(f"  {message}", flush=True),
        )
    except Exception as exc:
        # Avoid printing connection strings or raw account data from driver errors.
        print(f"Demo failed ({type(exc).__name__}). Run python run_tests.py for diagnostics.",
              file=sys.stderr)
        return 1
    print("PASS — scenario assertions verified.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
