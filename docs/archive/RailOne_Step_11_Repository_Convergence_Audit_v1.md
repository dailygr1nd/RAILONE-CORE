# RailOne Step 11 — Repository Convergence Audit

**Audit date:** 2026-07-14  
**Snapshot:** `repomix-output-dailygr1nd-RAILONE-CORE.xml`  
**Snapshot SHA-256:** `05a789ce6521847d2326886603d395852aa952312f8cb18b2df53522fb4e802b`  
**Target:** simulated domestic bank/M-PESA pilot with production-shaped execution semantics

## 1. Executive verdict

RailOne has a credible execution-semantics foundation in the cumulative Step 10
package. The UTT/RTT lineage, ContUID identity continuity, ETK authority,
idempotency, unknown-outcome handling, provider reconciliation, partner account
binding, settlement evidence, and finality-gated notification models are aligned
with the intended non-custodial architecture.

The repository itself is not yet converged. It contains two competing systems:

1. a legacy root-level prototype with committed private keys and older trust,
   execution, ledger, routing, adapter, and settlement implementations; and
2. ten cumulative step directories, of which Step 10 is the authoritative and
   complete current baseline.

Pilot convergence should promote Step 10 to the repository root, preserve prior
steps through Git history/tags rather than runtime folders, remove the legacy
runtime, rotate exposed keys, and then add the missing deployable sandbox
composition and security controls.

## 2. Evidence summary

- Files represented in snapshot: **701**
- Authoritative Step 10 files: **111**
- Exact duplicate groups: **101**
- Redundant duplicate instances: **377**
- Cumulative Step 01–09 files: **430**
- Step 10 tests rerun: **108 discovered, 101 passed, 7 expected skips**
- Skipped release gates: **4 optional FastAPI transport tests and 3 live
  PostgreSQL tests**
- Step 10 in the snapshot is content-equivalent to the previously validated
  package after line-ending normalization.

## 3. Architecture alignment

| RailOne principle | Snapshot assessment | Decision |
|---|---|---|
| Non-custodial execution | Preserved in Step 10; provider endpoints are resolved only at dispatch | Keep |
| P2P at the core | P2P is a first-class accepted origin and both participants can query the same UTT | Keep |
| Avia through merchant contexts | Merchant, branch, and partner scopes remain separate from human ContUIDs | Keep |
| Immutable intent, mutable execution | Signed UTT remains immutable; RTT birth evidence is immutable while operational outcome is separately versioned | Keep |
| Continuity identity | Stable ContUID/RIG/RIO plus append-only RIV trust changes are implemented | Keep |
| User-selected institutions/accounts | Opaque debit and credit bindings are snapshotted into quote/UTT semantics | Keep |
| Unknown provider outcome safety | Unknown outcomes suppress blind resubmission and require reconciliation | Keep |
| Settlement notification | Signed settlement evidence precedes deterministic sender/receiver SMS records | Keep |
| Cryptographic signatures | Step 10 uses purpose-separated, versioned Ed25519 signatures | Keep |
| Encryption/confidentiality | No production envelope-encryption implementation is present | Add in Step 11 |

## 4. Immediate security incident action

The following paths contain private key material and must be considered
compromised because they were committed and included in an AI-readable snapshot:

- `crypto/keys/BANK_KE.json`
- `crypto/keys/MPESA.json`
- `crypto/keys/R1CORE.json`
- `keys/BANK_KE_private.pem`
- `keys/BANK_TZ_private.pem`
- `keys/BANK_UG_private.pem`
- `keys/MPESA_private.pem`
- `keys/R1CORE_private.pem`
- `keys/SMOVE_private.pem`

Required response:

1. Revoke every corresponding public key or credential in every environment in
   which it was accepted.
2. Generate replacement keys outside the repository.
3. Remove the material from the current tree and rewrite Git history with a
   reviewed `git filter-repo` procedure.
4. Force all collaborators and deployment environments to re-clone or clean
   their histories after the rewrite.
5. Add secret scanning and pre-commit/CI rejection before accepting the cleanup
   pull request.

Deleting these files in a new commit is necessary but not sufficient because
older Git objects would still contain the private bytes.

## 5. Authoritative keep set

Promote the contents of `step_10_account_binding_notifications/` to the
repository root as the only pilot runtime:

- `railone_api/`
- `railone_authority/`
- `railone_callbacks/`
- `railone_contracts/`
- `railone_crypto/`
- `railone_execution/`
- `railone_history/`
- `railone_identity/`
- `railone_notifications/`
- `railone_operations/`
- `railone_partners/`
- `railone_postgres/`
- `railone_projection/`
- `railone_providers/`
- `migrations/0001` through `0006`
- `tests/`
- `docs/ADR-001` through `ADR-010`
- the Step 10 runbooks
- `pyproject.toml`
- `migrate.py`
- `run_tests.py`
- `dev_server.py` as explicitly gated local-only tooling
- `STEP_10_RELEASE_MANIFEST.md`

Do not renumber, squash, or delete migrations `0001`–`0006`. They form the
forward migration history and may already identify deployed database state.

## 6. Delete from the converged main branch

### Generated and duplicate files

- `desktop.ini`
- `step_07_postgresql_runtime/railone_pilot_baseline.egg-info/`
- `step_08_authenticated_api/railone_pilot_baseline.egg-info/`
- root `ACCOUNT-BINDING-SMS-RUNBOOK.md` because the identical canonical copy is
  under Step 10 `docs/`
- root `STEP_10_RELEASE_MANIFEST.md` if Step 10 is not yet promoted; after
  promotion retain exactly one copy
- all `__pycache__/`, `*.pyc`, `.pytest_cache/`, build, distribution, coverage,
  local database, and log artifacts if present outside the Repomix snapshot

### Cumulative development copies

Remove `step_01_*` through `step_09_*` from the converged main branch after the
Step 10 tag is verified. Their history remains available in Git. These folders
contain 430 files and reproduce older versions of the same packages, tests,
ADRs, and migrations.

### Compromised secrets

Remove `crypto/keys/` and `keys/` immediately, then purge their historical blobs
as described in section 4.

## 7. Archive, then remove from the pilot runtime

Create an immutable tag or archive branch such as
`archive/pre-convergence-root-prototype`, then remove these legacy root-level
modules from `main`:

- `adapters/`
- `compliance/`
- `crypto/`
- `execution/`
- `idempotency/`
- `identity/`
- `institutions/`
- `ledger/`
- legacy `migrations/` and `alembic.ini`
- `revenue/`
- `routing/`
- `settlement/`
- `webhooks/`
- legacy root Python scripts and simulation files
- `dashboard.html`
- the legacy root `requirements.txt`
- the legacy root `README.md`

The legacy code is not imported by Step 10. It also implements weaker trust
semantics, including filesystem private-key storage, less strict signed JSON,
hash-derived ETK behavior, and overlapping execution models. It should not be
available on the pilot import path.

Move any still-useful design prose from the old README and
`RailOne_Step_10_Account_Binding_and_Settlement_SMS_Spec_v1.md` into a reviewed
`docs/archive/` or supersession map before removing their root copies.

## 8. Security gap register

### P0 — Block cleanup merge or any sandbox credential use

1. **Committed private keys:** rotate, revoke, remove, and purge from history.
2. **Competing runtimes:** make Step 10 the only importable execution system.
3. **Secret controls:** add `.gitignore`, secret scanning, and CI enforcement.

### P1 — Block pilot traffic

1. **No deployable composition root:** the snapshot contains a local in-memory
   development server but no production-shaped application that wires
   PostgreSQL, KMS/Vault signing, callback processing, provider dispatch,
   reconciliation, outbox workers, SMS, and health/readiness checks.
2. **Seven environment gates still skipped:** install API dependencies and run
   all HTTP tests; run live migrations, repository tests, locking, rollback, and
   concurrency drills against disposable PostgreSQL.
3. **No at-rest application encryption:** implement AES-256-GCM envelope
   encryption for sensitive provider/contact resolver records and notification
   payloads, with KMS/Vault-managed key-encryption keys.
4. **Only test signing provider exists:** implement a KMS/HSM/Vault-backed
   `SigningKeyProvider` and continuity HMAC provider. Private keys must remain
   non-exportable.
5. **No TLS/mTLS deployment profile:** terminate TLS 1.3 at a hardened gateway
   and require mTLS for institution/service clients where supported.
6. **Partner authorization is not FAPI:** the handmade strict JWT verifier is a
   useful internal prototype, not an OAuth authorization server or FAPI 2.0
   deployment. Put institutional APIs behind a conformant implementation.
7. **M-PESA callback trust is gateway-local:** the HMAC is not a Safaricom
   signature. The trusted ingress needs TLS validation, source controls, rate
   limiting, request-size limits, timestamp/replay policy, and operational
   certification.
8. **Atomic finality drill outstanding:** prove callback application, RTT
   finality, settlement evidence, notification creation, and callback-inbox
   acknowledgement under worker crashes and concurrent duplicates.

### P2 — Required before production expansion

1. Dependency lock file, SBOM, vulnerability policy, SAST, and reproducible
   build provenance.
2. Central structured logging, traces, metrics, alert thresholds, and redaction
   tests.
3. Backup restore, disaster recovery, key rotation, and certificate rotation
   exercises.
4. PostgreSQL least-privilege roles and, where useful, row-level security or
   isolated service ownership.
5. Data classification, retention, legal hold, privacy deletion, and
   crypto-shredding policy compatible with append-only evidence.
6. Cross-language canonical-signing test vectors. The current strict JSON subset
   is deterministic, but external participants need a published versioned
   encoding contract or adoption of an interoperable canonicalization standard.
7. Crypto-agility registry for future ML-KEM/ML-DSA hybrid trials; do not replace
   Ed25519 during the pilot.

## 9. Pilot security profile

Adopt `R1-PILOT-SEC-1`:

- Ed25519 for RailOne-owned artifact signatures only;
- TLS 1.3 for all network traffic;
- mTLS for institutional and internal service communication where available;
- AES-256-GCM envelope encryption for sensitive application fields;
- HMAC-SHA-256 for ContUID derivation and trusted-ingress authentication with
  separate purpose-specific keys;
- short-lived access tokens with issuer, audience, purpose, expiry, revocation,
  and least-privilege scopes;
- synthetic identities, accounts, MSISDNs, balances, and institutions;
- isolated sandbox credentials and allowlisted outbound endpoints;
- production-equivalent idempotency, unknown-outcome, callback, reconciliation,
  retry, finality, audit, and key-rotation behavior;
- OWASP ASVS 5.0 Level 2 as the pilot application-verification baseline.

Do not weaken authentication or replay controls because money and identities
are simulated. Simulation should replace economic effects and personal data,
not the execution or security state machine.

## 10. Convergence sequence

1. Verify and push the Step 10 baseline commit.
2. Create `step-10-pilot-baseline` and a legacy archive tag/branch.
3. Revoke and rotate exposed keys before any sandbox credentials are activated.
4. Create a cleanup branch.
5. Promote Step 10 contents to the repository root.
6. Remove Steps 01–09, legacy root runtime, generated artifacts, duplicate docs,
   and compromised key files.
7. Replace the root README with a concise authoritative architecture and local
   execution guide.
8. Add secret scanning and dependency/build controls.
9. Run the complete test suite with optional API dependencies and disposable
   PostgreSQL; treat any skip as failure in CI.
10. Review the deletion diff against this manifest before merge.
11. Rewrite secret-bearing Git history in a separately reviewed maintenance
    operation and coordinate re-cloning.
12. Begin Step 11 implementation: deployable sandbox composition, encryption
    adapters, simulated bank/M-PESA effects, observability, and release gates.

## 11. Recommended cleanup commit

```text
refactor(repo): converge on the Step 10 pilot architecture

- promote the cumulative Step 10 packages to the repository root
- remove superseded Step 01-09 development copies
- archive and remove the legacy root execution stack
- remove duplicate, generated, and packaging artifacts
- remove committed private key files and block future secret commits
- retain the immutable migration, ADR, test, and runbook history
- establish one authoritative pilot build and test entrypoint

SECURITY: All keys previously committed under crypto/keys and keys are treated
as compromised and must be revoked, rotated, and purged from Git history.
```

## 12. Pilot readiness decision

**Current status: architecture-convergent prototype; not yet approved for pilot
traffic.**

Approval for a simulated integration pilot can follow when all P0 items are
closed, all 108 tests execute without skips, a disposable PostgreSQL run passes,
the deployable sandbox composition exists, sensitive fields are encrypted, and
the provider/callback crash-recovery drills pass.
