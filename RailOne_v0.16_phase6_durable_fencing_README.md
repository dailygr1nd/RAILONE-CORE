# RailOne v0.16 — Phase 6: Durable RTT/Economic Fencing and Bank Analytics Isolation

## Basis and patch compatibility

This additive patch is built against the supplied v0.16 Phase 4 Repomix snapshot **after** applying Phase 5 security hardening (migration `0014`). It introduces `0015` without modifying any prior migration.

**Installation is NOT approval for live money movement.** The current coordinator remains in `SIMULATED_PILOT` / `INSTITUTIONAL_SANDBOX` only. The new PostgreSQL adapter must be wired into a trusted deployment composition and pass PostgreSQL concurrency tests on a disposable server. The external bank no-effect proof verification/signing service is not provided by this patch.

## Contents

- `railone_postgres/fencing.py` — row-locked economic-effect reservations, RTT work records, signed no-effect release, settlement correlation and audit events
- `railone_institutions/admission.py` — registry-verified gateway now obtains the durable reservation before returning the adapter
- `railone_operations/service.py` — propagates provider observations without releasing economic holds
- `railone_crypto/signature_service.py` — adds purpose-separated `railone.no_effect_evidence` artifact type
- `railone_postgres/bank_analytics.py` — approved publication writer and bank-specific view reader
- `migrations/0015_durable_effect_fences_and_bank_analytics.sql` — three core fence/evidence tables plus events, tenant mappings, publication/withdrawal tables, row-security and guarded views
- `docs/ADR-021-durable-fencing-and-institution-intelligence-isolation.md` — invariants, role setup, open risks and required release gates
- `tests/test_durable_economic_fencing.py` — failure/replay/signed evidence and publication validation tests
- `tests/test_postgres_live.py` — disposable PostgreSQL locking, migration, release and distinct bank-login tests

## Apply safely (Windows PowerShell)

Confirm Phase 5 is merged and the working tree is clean:

```powershell
# Use the branch that actually contains migration 0014 (usually main after merge).
git switch main
git pull --ff-only origin main
git status --short
Test-Path .\migrations\0014_drop_plaintext_secret_fingerprints.sql
```

If the last command returns `False`, do **not** apply; return to your actual Phase 5 branch first.

```powershell
git switch -c feat/v0.16-durable-fencing-and-analytics
# Place the .patch in repository root; it is not committed automatically.
git apply --check .\RailOne_v0.16_phase6_durable_fencing_0015.patch
# If the compatibility check produces no errors:
git apply .\RailOne_v0.16_phase6_durable_fencing_0015.patch
$env:PYTHONDONTWRITEBYTECODE = "1"
python run_tests.py
python scripts/check_repository_convergence.py
python scripts/check_no_secrets.py
git diff --check
```

Expected **local without PostgreSQL**: `Ran 244 tests`, `OK (skipped=6)`; test counts can increase if your branch has other changes. **Six live database test cases must NOT be treated as verified.**

Commit only code/tests/docs, not the patch or ZIP bundle:

```powershell
git add railone_crypto/ railone_institutions/ railone_operations/
git add railone_postgres/ migrations/0015_durable_effect_fences_and_bank_analytics.sql
git add docs/ADR-021-durable-fencing-and-institution-intelligence-isolation.md
git add scripts/check_repository_convergence.py tests/
git diff --cached --check
git diff --cached --stat
git commit -m "security: add durable economic fences and bank metrics isolation"
git push -u origin feat/v0.16-durable-fencing-and-analytics
```

If the branch name already exists, switch to it rather than recreating it. If `git apply --check` fails, **do not force**; compare the real working tree with the Phase 5 source. The patch targets the exact reconstructed snapshot, not arbitrary future commits.

## Disposable PostgreSQL testing — never point to a real database

`tests/test_postgres_live.py` deliberately drops `railone_bank` and `railone` schemas during setup; **only use a newly created disposable DB with no real data**. You need a PostgreSQL 17 service and an authorized test database role with privileges to create schemas, temporary bank roles and related policy objects. The existing CI setup uses `postgres:17-alpine`.

```powershell
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:YOUR_TEST_PASSWORD@127.0.0.1:5432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pip install -e ".[pilot]"
python run_tests.py
```

This example DSN is a placeholder. Do not commit credentials or copy real bank data into the test server. Use a secrets manager for all deployed credentials. Expect **all 244 tests to execute with zero skips** when the PostgreSQL service/permissions are configured correctly; if tests fail, inspect the actual stack trace and fix before merge.

## Operational caveats

- `PostgresEconomicEffectFence` is a durable SQL component, not an independent authorizer by itself. Its use requires trusted UTT/RTT snapshots, valid signed wrappers, registry-verified adapters, a separately controlled settlement signer, and per-purpose database credentials.
- A reservation is sticky across crashes, restarts and timeouts; even `REJECTED` or `ACCEPTED_FOR_PROCESSING` does not clear it.
- A signed no-effect attestation must be based on independently authenticated external provider evidence. **Do not mint one merely to unblock a queue.**
- Bank-level access uses a dedicated PostgreSQL LOGIN per bank and a protected server-side mapping. Shared API credentials plus `SET ROLE`/user-supplied bank IDs are insufficient. `railone_bank.metrics` is the only read interface for the bank reader role.
- Row-level security protects the published analytics table, not every RailOne operational table. The database administrator must separately provision least-privileged execution, reconciliation, secrets, and analytics publisher roles.
- The new analytics metric publisher only accepts structured, reviewed own-bank counters/latency. It does not automatically compute the correct population or verify a human approval; that trusted aggregator remains outstanding.
- Verify the new server's deployment, network policy, migration/restore behavior, cross-login visibility, and callback/settlement concurrency before enabling any partner integration.
