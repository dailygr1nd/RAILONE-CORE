# RailOne Pilot Convergence - Step 10

This cumulative batch contains the cryptographic, identity, and execution-
authority, commercial-contract, and deterministic execution baselines. It adds
operational ContUID lookup and transaction views, replay-safe provider
submission, stable provider idempotency, and Ed25519-signed execution events.
Step 07 adds PostgreSQL repository adapters, checksum-locked migrations,
explicit transaction ownership, and exactly-once provider-progress projection.
Step 08 adds the authenticated API boundary, token-derived actor scopes,
revocation, rate limiting, signed request audit, and an optional FastAPI
transport. Step 09 freezes the first execution integration to M-PESA Kenya
Daraja B2C sandbox for domestic KES and adds correlated callback reconciliation.
Step 10 binds user-selected partner institutions and opaque debit/credit account
bindings into the UTT and adds signed-settlement sender/receiver SMS semantics.

## Step 10 outcome

- Active partner institutions can be filtered by country, currency, and account
  role.
- Onboarding creates reusable opaque account bindings; every intent selects a
  debit and credit binding.
- Quotes fail closed without a partner endpoint validator.
- Signed quotes and UTTs contain endpoint snapshots and no provider-ready raw
  account references.
- Routes cannot change the selected source or destination institution.
- Revoked bindings block a new RTT without mutating the UTT.
- Provider endpoints are resolved only through an isolated resolver boundary.
- Correlated provider success creates Ed25519-signed settlement evidence.
- Settlement evidence atomically creates one sender and one receiver SMS record.
- SMS bodies use the UTT reference, safe party display names, institution name,
  masked account hint, accepted amounts, fee, and explicit timezone.
- An uncertain SMS gateway outcome is terminal `UNKNOWN` and is not resent
  automatically.
- PostgreSQL tables and guards cover partner bindings, settlement evidence, and
  SMS delivery state.

## Step 09 outcome

- `MPESA-KE` accepts only mobile-money, KES-to-KES, equal whole-KES amounts and
  normalized Kenyan beneficiary MSISDNs.
- OAuth failure before the B2C call is retryable; an uncertain payment call is
  unknown and blocks rerouting.
- M-PESA is explicitly treated as having no RailOne-verifiable provider-side
  idempotency guarantee. Recovery from durable `DISPATCHING` makes no second
  provider call.
- Immediate Daraja acceptance is `ACCEPTED_FOR_PROCESSING`, never beneficiary
  credit or settlement.
- Callback correlation binds `ConversationID`, `OriginatorConversationID`, the
  dispatched amount, `TransactionID`, and receipt evidence.
- The callback inbox stores only normalized allowlisted data and rejects a
  changed replay under the same provider event ID.
- Queue timeout moves the existing RTT to `RECONCILIATION_REQUIRED`; a late
  correlated result resolves that same attempt without creating a second route.
- The optional HTTP surface exposes result and timeout handlers only when an
  M-PESA callback processor is explicitly wired.
- Callback HMAC is an internal trusted-ingress control, not a claimed native
  Safaricom signature. Provider connectivity/certification remains a pilot gate.

## Step 08 outcome

- Access tokens are Ed25519 JWTs signed only by `ACCESS_TOKEN_SIGNING` keys.
- Tokens are short-lived, issuer/audience checked, key-lifetime bound, and
  revocable by token ID.
- ContUID, merchant, branch, and partner scopes stay separate inside the token.
- Request parameters select targets but never grant actor authority.
- Privileged reads require both `railone.transactions.read:any` and a reason.
- Provider-submission visibility first proves access to its UTT.
- Per-principal/route limits are atomic in PostgreSQL.
- Allowed, denied, rate-limited, and failed guarded requests produce signed,
  append-only API audit artifacts without bearer-token material.
- RailOne exposes no public token-minting or bootstrap-owner endpoint.
- The optional HTTP surface provides `/v1/auth/me`, exact UTT reads, scoped
  history, and provider-outcome reads.

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
- `railone_api/auth.py` - Ed25519 JWT issuance/verification, actor scopes, and
  token revocation contracts.
- `railone_api/guard.py` - rate limiting and signed request audit.
- `railone_api/facade.py` - transport-independent authenticated API operations.
- `railone_api/http.py` - optional FastAPI transport.
- `railone_postgres/api_security.py` - PostgreSQL revocation, rate-limit, and
  request-audit stores.
- `migrations/0004_authenticated_api_security.sql` - durable API security state.
- `docs/ADR-008-authenticated-api-boundary.md` - Step 08 decision.
- `tests/test_api_authentication.py` and `tests/test_authenticated_api_facade.py`
  - token, scope, audit, and limit tests.
- `tests/test_http_transport.py` - optional HTTP smoke tests.
- `railone_providers/mpesa.py` - Daraja OAuth and B2C sandbox adapter.
- `railone_callbacks/` - trusted-ingress authentication, normalization,
  correlation, idempotency, and RTT reconciliation.
- `railone_postgres/callbacks.py` - durable sanitized callback inbox.
- `migrations/0005_mpesa_callback_reconciliation.sql` - provider correlation
  context and reconciliation transition guard.
- `docs/ADR-009-mpesa-kenya-sandbox-boundary.md` - Step 09 trust and outcome
  semantics.
- `docs/MPESA-SANDBOX-RUNBOOK.md` - sandbox setup and failure-drill checklist.
- `tests/test_mpesa_adapter.py` and `tests/test_mpesa_callbacks.py` - provider,
  replay, correlation, HMAC, amount, timeout, and late-result tests.
- `railone_partners/` - active institution discovery and opaque binding checks.
- `railone_operations/endpoints.py` - isolated provider endpoint resolver.
- `railone_notifications/` - signed settlement evidence, templates, and SMS relay.
- `railone_postgres/partners.py` and `railone_postgres/notifications.py` - durable
  Step 10 stores.
- `migrations/0006_partner_bindings_settlement_notifications.sql` - partner,
  binding, settlement, and SMS schema guards.
- `docs/ADR-010-partner-account-binding-and-settlement-notifications.md` - Step
  10 decision.
- `docs/ACCOUNT-BINDING-SMS-RUNBOOK.md` - onboarding and notification drills.
- `tests/test_partner_account_bindings.py` and
  `tests/test_settlement_notifications.py` - Step 10 safety tests.

## Run the tests

From this directory:

```bash
python run_tests.py
```

From the parent `RAILONE PROTOTYPE` directory in PowerShell:

```powershell
python .\step_10_account_binding_notifications\run_tests.py
```

For an editable local installation, run this once inside the Step 10 directory:

```powershell
python -m pip install -e .
```

That makes the `railone_*` packages importable for direct scripts as well as
through the bundled runner.

Do not use `python -m unittest discover -s tests` from the parent directory;
there is no parent-level `tests` package. The runner resolves the Step 10 project
root automatically and avoids the `ModuleNotFoundError` seen when a nested test
file is invoked directly without installing the package.

For the complete pilot runtime dependencies:

```powershell
python -m pip install -e ".[pilot]"
$env:RAILONE_DATABASE_URL = "postgresql://YOUR_REAL_USER:YOUR_REAL_PASSWORD@localhost:5432/YOUR_RAILONE_DB"
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

For a localhost-only HTTP smoke test using ephemeral in-memory keys and stores:

```powershell
$env:RAILONE_ALLOW_IN_MEMORY_DEV_SERVER = "1"
python .\dev_server.py
```

The server prints a 15-minute development token and binds only to
`127.0.0.1:8080`. This mode is not a pilot deployment profile.

## Integration rule

Do not connect this batch to the legacy `crypto/keys/*.json` files. Those keys
were present in the uploaded repository snapshot and must be treated as
compromised. Production integration must supply a `SigningKeyProvider` backed
by an isolated signer, HSM, KMS-compatible service, or Vault-like service.

The in-memory signing and continuity-secret providers are explicitly test-only.
Production adapters must use isolated key services and a durable repository with
a unique constraint on the keyed identity fingerprint.

Step 09 adds exactly one provider sandbox adapter and verified callback inbox
processing for the frozen pilot corridor. Before connecting it, follow
`docs/MPESA-SANDBOX-RUNBOOK.md` and verify the exact B2C product/version inside
the authenticated Daraja application.

The included environment did not contain a configured disposable PostgreSQL
server, so live database checks skip cleanly. The suite verifies repository
contracts, transaction rollback, serialization, locking SQL, signed projection,
callback replay, and migration structure without claiming that the live
PostgreSQL release gate has passed. Run live migration, upgrade, callback
concurrency, and worker-crash drills before sandbox traffic.
