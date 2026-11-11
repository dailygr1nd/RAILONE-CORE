# ADR-025 — Institutional HTTP-to-PostgreSQL sandbox conformance

**Status:** Proposed sandbox test gate; not production certification.

## Decision

Retain the established RailOne v0.16 execution engine, immutable UTT, RTT
fencing and signed institutional dispatch admission. Add an end-to-end test that
starts with **real authenticated FastAPI HTTP routes** and then uses the
existing internal provisioner for ExecutionPlan, RTT, authorized adapter
registration and dispatch. Never expose private routing operations as
unauthenticated HTTP endpoints solely for demonstration.

This proof uses an **in-process ASGI TestClient**, not a running public server or
an independently developed bank client. Key material, identities, endpoints,
manifests and provider outcomes are synthetic.

## Flow

1. Sender signs ETK-S independently with their synthetic Ed25519 key.
2. Sender's scoped bearer token verifies ETK-S via HTTP.
3. Receiver independently signs ETK-R bound to the exact ETK-S digest.
4. Receiver's distinct scoped bearer token verifies ETK-R via HTTP.
5. A compromised aggregator principal attempts to impersonate the sender; 403.
6. A modified quote amount is submitted to UTT acceptance; 403.
7. Sender creates UTT over authenticated HTTP with a unique idempotency key.
8. Repeating exactly that request/key returns the same UTT without a new effect.
9. The PostgreSQL-backed plan and RTT are created for the same UTT.
10. An authorized synthetic institutional adapter receives a signed dispatch
    wrapper only after a durable economic-effect fence is reserved.
11. A recreated dispatcher cannot redispatch that RTT. Timeout and crash
    scenarios leave the economic hold fenced until verified resolution.
12. API audit rows (including both denial decisions) and effect fence records
    are verified in the disposable PostgreSQL database.

`ACCEPTED_FOR_PROCESSING` is not settlement; settlement evidence count remains
zero for these scenarios. No duplicate payment is claimed or inferred from
provider idempotency alone.

## How to run

Set `RAILONE_TEST_DATABASE_URL` to a disposable PostgreSQL database, set
`RAILONE_ALLOW_TEST_SCHEMA_RESET=1` and `RAILONE_REQUIRE_LIVE_POSTGRES=1`.
`demo_sandbox.py` **drops and rebuilds** the `railone` and `railone_bank`
schemas. Never point it at shared or production infrastructure.

```powershell
python -m pip install -e ".[pilot]"
python -m unittest -v tests.test_postgres_live.LivePostgresRuntimeTests.test_v017_http_to_postgres_institutional_dispatch
python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario accepted --report-json v017-accepted.json
python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario timeout --report-json v017-timeout.json
python demo_sandbox.py --reset-disposable-db --http-bilateral --scenario crash --report-json v017-crash.json
```

Each demo resets the same disposable schemas; run serially. Do not run the
full test suite in parallel against the same disposable DB.

## Still required before a true externally deployed institutional pilot

- Run all live PostgreSQL tests without skips against the target merged branch.
- Deploy the HTTP application behind properly configured TLS/mTLS, authentication,
  rate limits and institution-managed cryptographic keys.
- Replace TestClient with independent network clients and independently
  implemented adapters for both sides of an institutional corridor.
- Prove authentic settlement evidence and finality/reconciliation behavior;
  synthetic provider acceptance alone does not satisfy that requirement.
- Exercise concurrency, recovery, operator approval and revocation across
  multiple processes, hosts and authenticated counterparties.

Do not claim production-ready institutional settlement from this conformance
proof alone.
