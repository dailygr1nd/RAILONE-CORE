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
    parser.add_argument(
        "--http-bilateral", action="store_true",
        help="Use authenticated in-process HTTP for ETK-S, ETK-R and UTT before dispatch.",
    )
    parser.add_argument(
        "--report-json", metavar="PATH",
        help="Write a sanitized machine-readable evidence report on success.",
    )
    parser.add_argument("--delegated", action="store_true", help="Use beneficiary-mandated institutional acceptance.")
    parser.add_argument("--reconcile-no-effect", action="store_true",
                        help="Resolve a timeout using a synthetic signed no-effect attestation.")
    args = parser.parse_args()
    if args.reconcile_no_effect and args.scenario != "timeout":
        parser.error("--reconcile-no-effect requires --scenario timeout")
    if args.delegated and not args.http_bilateral:
        parser.error("--delegated requires --http-bilateral")
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
    messages = []

    def report(message):
        messages.append(message)
        print(f"  {message}", flush=True)

    try:
        LivePostgresRuntimeTests.setUpClass()
        exercise_institutional_dispatch(
            test, PostgresDatabase(test.factory), scenario=args.scenario,
            report=report,
            http_bilateral=args.http_bilateral, delegated=args.delegated, reconcile_no_effect=args.reconcile_no_effect,
        )
    except Exception as exc:
        # Avoid printing connection strings or raw account data from driver errors.
        print(f"Demo failed ({type(exc).__name__}). Run python run_tests.py for diagnostics.",
              file=sys.stderr)
        return 1
    if args.report_json:
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        path = Path(args.report_json)
        evidence = {
            "protocol": "RAILONE",
            "profile": "V0.18_DELEGATED_SANDBOX" if args.delegated else "V0.17_INSTITUTIONAL_SANDBOX",
            "custody_model": "NON_CUSTODIAL",
            "transport": "IN_PROCESS_ASGI_HTTP" if args.http_bilateral else "INTERNAL_FIXTURE",
            "scenario": args.scenario,
            "result": "PASS",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": messages,
            "warning": "Synthetic test evidence only; not proof of real settlement or production readiness",
        }
        path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"  Evidence report: {path}", flush=True)
    print("PASS — scenario assertions verified.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
