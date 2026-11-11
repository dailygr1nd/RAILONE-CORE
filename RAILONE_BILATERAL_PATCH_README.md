# RailOne v0.16 — Receiver-First ETK/UTT/RTT & Compromised Institution Harness

**Base:** Uploaded RailOne v0.16 Repomix snapshot, reconstructed as editable repository files. This is a proposed change set, **not** a GitHub commit or merged PR.

## What changes

- Adds `railone_authority/bilateral.py`: signed receiver-first ETK-R v2, separately signed sender ETK-S v2, quote/endpoint/digest ownership and expiration verification.
- Extends quote acceptance to accept **both independently signed authorities before creating the UTT**, and persist both authorities atomically in the existing accepted-UTT transaction.
- Enforces v2 verification at route planning, RTT creation, and trusted institutional dispatch-snapshot generation.
- Makes the deployed institutional sandbox dispatcher require v2 by default (`require_receiver_first=True`). Existing legacy fixtures opt out explicitly.
- Detects provider request/body substitutions by recalculating SHA-256 from the actual provider request, including protected account endpoint references.
- Adds redacted, append-only PostgreSQL audit events (`migration 0016`) and denial logging to the relevant boundaries.
- Adds synthetic compromised-institution conformance tests, runnable JSONL harness, and a disposable PostgreSQL live test.

## Apply this patch in a clean RailOne checkout

Create a feature branch, then copy the accompanying `.patch` into the repository root or choose its absolute path.

```powershell
git checkout -b feat/receiver-first-bilateral-security
git apply --check .\RailOne_v0.16_receiver_first_security.patch
git apply .\RailOne_v0.16_receiver_first_security.patch
python -m pip install -e ".[pilot]"
python scripts/run_compromised_institution_harness.py
python run_tests.py
```

If the patch lives outside the repository, substitute its actual file path in `git apply`. Do not apply to the extracted Repomix XML, historical `step_*` directories, or `reference_source`/`source` development copies.

For database-backed validation, see `docs/ADR-022-receiver-first-bilateral-and-compromise-harness.md`. Live integration tests **reset `railone` and `railone_bank` schemas**; connect only to a disposable database.

## Verification from this environment

- Unit/synthetic suite: 269 tests run, 259 passed, 10 skipped, zero failures **before final packaging**. Re-run after applying.
- Live PostgreSQL: not run here (disposable Docker/PostgreSQL runtime unavailable).
- JSONL harness emits scenario results and redacted security decisions; those local events are synthetic observations, not PostgreSQL audit records.

## Known follow-up before real partner traffic

- Wire the strict acceptance sequence into authenticated HTTP/client flows and require issuer/delegation policy from a validated registry.
- Exercise all new tests against disposable PostgreSQL, including worker concurrency and crash recovery.
- Independent adapter certification and validated bank/provider evidence.
- Quarantine orchestration, independent security log replication, production key custody and operational incident response.

**Do not merge as a live-money security certification.**
