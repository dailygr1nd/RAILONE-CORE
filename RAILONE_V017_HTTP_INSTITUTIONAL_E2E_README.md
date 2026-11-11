# RailOne v0.17 — authenticated HTTP → PostgreSQL → institutional dispatch

**Incremental test-and-demo patch** for your merged v0.16 authenticated-bilateral-API branch. It adds no new migrations and changes no production dispatch rules.

## Safety

This package exercises synthetic bank participants, test-only ephemeral Ed25519 keys, an in-process ASGI HTTP client, and a single certified synthetic institutional adapter. It **does not** establish live settlement, real network-hosted connectivity, or two independently developed institutional adapters.

The demo and integration tests drop and rebuild the `railone` and `railone_bank` schemas. **Never use a shared, staging, or production database.**

## Apply to clean main

```powershell
git switch main
git pull --ff-only
git status --short
git switch -c feat/v0.17-institutional-http-e2e

git apply --check .\RailOne_v0.17_http_postgres_institutional_e2e.patch
git apply .\RailOne_v0.17_http_postgres_institutional_e2e.patch
```

Run using your existing disposable Docker container:

```powershell
docker start railone-pg-disposable
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

python -m pip install -e ".[pilot]"
python -m unittest -v tests.test_postgres_live.LivePostgresRuntimeTests.test_v017_http_to_postgres_institutional_dispatch
python run_tests.py
```

Expected discovery count: **292 tests**. With all optional deps installed and the disposable database available, the target is `OK` with **no skips**; this target is not yet validated in this environment.

## Run the three synthetic demo scenarios

Run sequentially; each scenario resets the same disposable schemas:

```powershell
python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario accepted --report-json v017-accepted.json
python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario timeout --report-json v017-timeout.json
python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario crash --report-json v017-crash.json
```

On success, each JSON report contains a synthetic pass record and redacted check descriptions, not private credentials, account numbers, raw ETK payloads, or claims about external settlement. The `accepted` scenario means the adapter accepted the request **for processing**, not that money settled.

## Validation performed by the implementer

- Source compiles.
- 292 tests discovered; 279 passed and 13 skipped locally because PostgreSQL and its driver are unavailable in this runtime (10 previously skipped integration tests plus 3 new ones).
- Repository convergence and secret scanning passed after removing generated `__pycache__` artifacts.
- Patch applies cleanly against the previous authenticated API working copy and reproduces all changed files byte-for-byte.

**Still required from you:** the full live PostgreSQL suite and all three v0.17 demo scenarios. Do not merge on only the local skipped suite.

## Why one adapter?

This gate exercises two independent human signing authorities and two logical banking endpoints, but a *single* synthetic reference adapter. The next independent-adapter certification gate must use distinct institution-owned implementations and network clients.
