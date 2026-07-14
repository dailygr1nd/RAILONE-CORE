# RailOne Pilot Convergence - Step 07

This cumulative batch contains the cryptographic, identity, and execution-
authority, commercial-contract, and deterministic execution baselines. It adds
operational ContUID lookup and transaction views, replay-safe provider
submission, stable provider idempotency, and Ed25519-signed execution events.
Step 07 adds PostgreSQL repository adapters, checksum-locked migrations,
explicit transaction ownership, and exactly-once provider-progress projection.

## Step 07 outcome

- Durable adapters now cover identity continuity, accepted contracts,
  ExecutionPlans/RTTs, permissioned transaction history, provider operations,
  the signed outbox, and provider-progress projections.
- ExecutionPlan birth material stays immutable while evolving route and failure
  state is persisted separately under optimistic concurrency.
- Outbox claims use PostgreSQL row locks, `SKIP LOCKED`, expiring leases, and
  compare-and-swap updates.
- Signed provider events are verified and deduplicated before projection.
- Delayed events cannot regress the current provider state.
- Provider acceptance is explicitly `ACCEPTED_FOR_PROCESSING`, never settlement
  success.
- Migration bytes are SHA-256 locked and one migrator runs at a time.

## What this step locks

- Ed25519 is the canonical signature algorithm for RailOne-owned artifacts.
- Ed25519 signs data; it does not encrypt data.
- Private keys are never stored in the repository or returned by the key
  registry.
- Every signature carries an algorithm, curve, key identifier, artifact type,
  version, issuer, issue time, and payload hash.
- Quote, execution, identity, settlement, and replay signing are separate key
  purposes.
- JSON payloads are serialized deterministically and floating-point numbers are
  rejected from signed financial artifacts.
- Key rotation and revocation are part of verification semantics.
- A RailOne continuity identifier is derived from a versioned keyed digest and
  contains 160 bits of collision-resistant output.
- Raw national identifiers and raw provider subject identifiers are not stored
  in identity continuity objects.
- RIG is immutable genesis evidence, RIO is the stable public continuity object,
  and RIV contains mutable trust evolution.
- Institutional identity claims require a valid Ed25519 attestation.
- ETK-S is a signed sender execution-authority attestation bound to a UTT and
  accepted quote.
- ETK-R is signed receiver participation or eligibility evidence and cannot be
  fabricated merely by hashing ETK-S.
- Passive-credit and pre-authorized beneficiary flows do not falsely claim that
  a receiver actively confirmed.
- A quote is a signed, expiring commercial offer and does not bind execution to
  a specific rail.
- A UTT can only be created after explicit acceptance of a valid quote.
- Quote acceptance creates the UTT and ETK-S as one atomic contract record.
- One accepted quote cannot produce multiple UTTs.
- Idempotency-key reuse with different request material is rejected.
- UTT commercial payloads and signed envelopes are deeply immutable in memory.
- Customer pricing is `PER_INTENT`, preserving one charge across all future RTT
  attempts.
- An ExecutionPlan can only be created for a persisted, valid signed UTT.
- Route eligibility rejects down links, stale or future telemetry, currency and
  amount mismatches, insufficient liquidity, and routes outside the budget.
- Route ranking is deterministic, integer-only, and uses a stable route-ID tie
  break.
- Every RTT is Ed25519-signed and preserves its UTT, plan, attempt, prior RTT,
  and prior route lineage.
- An RTT is an immutable birth artifact; outcome state evolves in a separate
  attempt record.
- Retryable, terminal, and reconciliation-required failures are distinct.
- Unknown provider outcomes block retry to prevent duplicate payments.
- The UTT holds the one customer charge; RTTs contain no customer-fee fields.
- RIG remains immutable, RIO retains stable identity fields, and trust/status
  evolution appends RIVs rather than overwriting prior identity state.
- A known ContUID can resolve its current identity projection and full RIV
  history.
- Sender and receiver ContUIDs can independently find the same P2P UTT with
  their correct participant roles.
- Exact UTT lookup and ContUID transaction-history lookup require participant,
  commercial-scope, or explicitly reasoned privileged access.
- Allowed and denied transaction reads produce append-only access-audit records.
- Merchant, branch, and partner identifiers remain commercial actor scopes and
  are not coerced into human ContUIDs.
- Transaction projections omit account references and raw provider subjects.
- Provider execution requests are prepared only from a current signed RTT and
  its persisted signed UTT.
- Provider idempotency keys are stable per provider and RTT.
- `ACCEPTED` provider submission is not confused with successful settlement.
- Known rejections require explicit retryable or terminal disposition.
- Adapter exceptions become unknown outcomes and suppress automatic resubmit.
- Every provider transition emits an Ed25519-signed execution event.
- Outbox delivery uses worker leases, bounded retry, and dead-letter semantics;
  consumers deduplicate the at-least-once stream by event ID.

## Files

- `docs/ADR-001-railone-pilot-baseline.md` - authoritative architecture decision.
- `railone_crypto/canonical_json.py` - strict deterministic JSON encoding.
- `railone_crypto/key_provider.py` - key metadata and signer/registry contracts.
- `railone_crypto/signature_service.py` - signed artifact envelopes and verification.
- `tests/test_signature_service.py` - deterministic, tamper, purpose, lifecycle,
  and serialization tests.
- `railone_identity/` - deterministic continuity and attestation validation.
- `railone_authority/` - signed ETK-S and ETK-R issuance.
- `tests/test_identity_continuity.py` - identity and attestation tests.
- `tests/test_execution_authority.py` - ETK binding and participation tests.
- `railone_contracts/` - quote, origin-context, acceptance, UTT, and store contracts.
- `tests/test_quote_acceptance.py` - quote and UTT invariant tests.
- `docs/ADR-004-execution-plan-and-rtt.md` - authoritative Step 04 decision.
- `railone_execution/models.py` - immutable route, plan, failure, and RTT records.
- `railone_execution/scoring.py` - deterministic eligibility and route scoring.
- `railone_execution/store.py` - transactional persistence boundary and test adapter.
- `railone_execution/service.py` - plan construction and RTT lifecycle services.
- `tests/test_execution_plan_rtt.py` - routing, retry, lineage, and safety tests.
- `pyproject.toml` - editable-install metadata and runtime dependency declaration.
- `docs/ADR-005-continuity-transaction-history.md` - identity/history decision.
- `railone_history/` - UTT subject indexing and permissioned history queries.
- `migrations/0001_identity_transaction_history.sql` - PostgreSQL identity,
  accepted-UTT, subject-link, and access-audit schema.
- `tests/test_continuity_transaction_history.py` - P2P, merchant-scope, privacy,
  access-control, audit, and idempotency tests.
- `railone_operations/` - provider request, normalization, signed outbox, and relay.
- `migrations/0002_execution_provider_outbox.sql` - durable plans, RTTs,
  provider submissions, callback inbox, outbox, and reconciliation schema.
- `docs/ADR-006-provider-submission-and-outbox.md` - provider safety decision.
- `docs/JULY-31-PILOT-RELEASE-PLAN.md` - frozen scope, schedule, and release gates.
- `tests/test_provider_operations.py` - dispatch and outbox safety tests.
- `railone_postgres/` - PostgreSQL runtime, codecs, migrations, and repository
  adapters.
- `railone_projection/` - signed exactly-once provider outcome projection.
- `migrations/0003_postgres_runtime_projection.sql` - mutable plan state and
  projection tables.
- `docs/ADR-007-postgresql-runtime-and-outcome-projection.md` - Step 07 decision.
- `tests/test_postgres_runtime.py` - transaction, codec, migration, and locking
  contract tests.
- `tests/test_provider_outcome_projection.py` - signature, replay, ordering, and
  settlement-semantics tests.

## Run the tests

From this directory:

```bash
python run_tests.py
```

From the parent `RAILONE PROTOTYPE` directory in PowerShell:

```powershell
python .\step_06_durable_outbox_provider_boundary\run_tests.py
```

For an editable local installation, run this once inside the Step 07 directory:

```powershell
python -m pip install -e .
```

That makes the `railone_*` packages importable for direct scripts as well as
through the bundled runner.

Do not use `python -m unittest discover -s tests` from the parent directory;
there is no parent-level `tests` package. The runner resolves the Step 07 project
root automatically and avoids the `ModuleNotFoundError` seen when a nested test
file is invoked directly without installing the package.

For PostgreSQL runtime support:

```powershell
python -m pip install -e ".[postgres]"
$env:RAILONE_DATABASE_URL = "postgresql://railone:password@localhost:5432/railone"
python .\migrate.py
```

Use a secret manager for the real DSN. Do not commit credentials.

The live integration test resets the `railone` schema. Run it only against a
disposable test database:

```powershell
$env:RAILONE_TEST_DATABASE_URL = "postgresql://YOUR_REAL_USER:YOUR_REAL_PASSWORD@localhost:5432/YOUR_DISPOSABLE_TEST_DB"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
python .\run_tests.py
```

The username, password, and database above are placeholders; replace all three
with credentials that already exist in PostgreSQL. If the database is
unavailable, the live tests skip cleanly. For a CI or release gate where a skip
must fail the build, also set:

```powershell
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
```

## Integration rule

Do not connect this batch to the legacy `crypto/keys/*.json` files. Those keys
were present in the uploaded repository snapshot and must be treated as
compromised. Production integration must supply a `SigningKeyProvider` backed
by an isolated signer, HSM, KMS-compatible service, or Vault-like service.

The in-memory signing and continuity-secret providers are explicitly test-only.
Production adapters must use isolated key services and a durable repository with
a unique constraint on the keyed identity fingerprint.

Step 08 should add authenticated APIs, token-derived actor scopes, request
auditing, and rate-limit boundaries. Step 09 should add one provider sandbox
adapter and verified callback inbox processing.

The included environment did not contain a PostgreSQL server or psycopg, so the
Step 07 suite verifies repository contracts, transaction rollback, serialization,
locking SQL, signed projection, replay, and migration structure without claiming
that the live PostgreSQL release gate has passed. Run live database integration,
upgrade, and concurrency drills in the deployment environment before sandbox
traffic.
