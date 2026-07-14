# RailOne Core

RailOne is a non-custodial execution-continuity engine. It accepts a signed
financial intent, selects an eligible route, submits an execution request to an
existing financial rail, and preserves deterministic evidence through finality
or reconciliation.

This repository is the cumulative Step 11E pilot baseline. It adds a signed
partner certification harness to Step 11D's version-pinned institution adapter
SPI. Partner sandbox executions produce canonical traces that RailOne evaluates
for execution ordering, replay safety, evidence finality, history authorization,
notification gating, adapter pinning and sensitive-data minimization. The
package is safe to overlay without deleting legacy files.

## Core invariants

- P2P transfers are first-class RailOne intents.
- Avia and other commerce systems enter through merchant, branch, or partner
  contexts rather than being coerced into human ContUIDs.
- A quote is a signed, expiring commercial offer.
- Explicit quote acceptance creates one immutable UTT and sender authority.
- RTTs are signed immutable attempt-birth artifacts; operational state is
  versioned separately.
- Unknown provider outcomes block blind retry and require reconciliation.
- RailOne resolves provider-ready account endpoints only at dispatch.
- Provider acceptance is never described as settlement.
- Every RTT pins one exact adapter id and semantic version; a retry cannot
  silently change adapter implementation.
- Adapter capability manifests are Ed25519-signed and append-only.
- Institution adapters normalize external evidence; RailOne core owns UTT/RTT,
  retry, finality and transaction-history truth.
- Synthetic harness self-tests are never signable as partner evidence.
- Only a verified, active adapter manifest and partner-sandbox trace driver can
  produce an Ed25519-signed certification report.
- Sender and receiver SMS records are created only from signed settlement
  evidence.
- RailOne never takes custody of customer funds.

## Repository map

| Area | Responsibility |
|---|---|
| `railone_identity/` | ContUID, immutable identity genesis, and mutable trust revisions |
| `railone_authority/` | ETK-S and ETK-R execution authority |
| `railone_contracts/` | Quote acceptance and immutable UTT contracts |
| `railone_execution/` | Deterministic plans, RTT lineage, retry and reconciliation |
| `railone_operations/` | Provider dispatch, idempotency and signed outbox |
| `railone_institutions/` | Signed adapter SPI, registry, codecs, transport and reference profiles |
| `railone_callbacks/` | M-PESA callback normalization and correlation |
| `railone_certification/` | Capability-aware partner scenarios, trace evaluation and signed reports |
| `railone_partners/` | Partner institutions and opaque account bindings |
| `railone_notifications/` | Settlement evidence and finality-gated SMS |
| `railone_postgres/` | Durable PostgreSQL repository adapters |
| `railone_api/` | Authenticated visibility boundary |
| `railone_security/` | AES-256-GCM envelopes and isolated key-service boundary |
| `railone_sandbox/` | Deterministic bank/M-PESA synthetic effects and readiness |
| `migrations/` | Immutable forward database history |
| `docs/` | ADRs, runbooks and security profile |

## Local verification

From the repository root:

```powershell
python -m pip install -e ".[pilot]"
python .\scripts\check_repository_convergence.py
python .\scripts\check_no_secrets.py
python .\run_tests.py
```

For the live PostgreSQL gates, use a disposable database only:

```powershell
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:5432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
python .\run_tests.py
```

The live test resets the `railone` schema. Never point it at a persistent or
shared database.

## Security boundary

Ed25519 signs RailOne artifacts; it does not encrypt data. The pilot security
profile is defined in `docs/SECURITY-PROFILE-R1-PILOT-SEC-1.md`.

The repository contains only test in-memory key providers. A deployed sandbox
must supply isolated signing, continuity-secret, and envelope-key services.
Private keys,
provider credentials, access tokens, contact endpoints, and real account
identifiers must never be committed.

Any key previously stored under the legacy `crypto/keys/` or `keys/` paths is
compromised and must be revoked, rotated, and purged from Git history.

## Current release status

The codebase is an architecture-convergent prototype with deployable simulated-
pilot security and provider-effect boundaries. It is eligible for a simulated
integration pilot only after CI executes all tests without skips, including the
optional HTTP and disposable PostgreSQL gates. It is not a live-funds or
production deployment profile.

The detailed Step 10 baseline remains available at
`docs/STEP-10-BASELINE.md`.
