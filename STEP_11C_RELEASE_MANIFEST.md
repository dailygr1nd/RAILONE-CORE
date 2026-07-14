# Step 11C release manifest

- Build date: July 14, 2026
- Package version: 0.13.0
- Custody model: non-custodial
- Signature baseline: Ed25519 through an external isolated signer
- At-rest confidentiality: versioned AES-256-GCM envelope encryption
- Effect model: durable synthetic `BANK-KE` and `MPESA-KE`
- Migration chain: immutable `0001` through `0008`
- Runtime restriction: `SIMULATED_PILOT`

## Added controls

- encrypted PostgreSQL notification-body persistence;
- encrypted M-PESA/provider credential resolver;
- durable simulated-effect scheduling and persisted logical clock;
- effect leases, expiry reclamation, retry availability and dead letters;
- stale-worker acknowledgement rejection;
- bounded worker supervision and readiness reporting;
- PostgreSQL-backed deployment composition with isolated encryption keys;
- migration-0008 readiness gate; and
- ADR-012 and Step 11C deployment runbook.

## Verification result

- Tests discovered: 132
- Tests passed with HTTP dependencies installed: 129
- Environment-gated tests skipped: 3 disposable PostgreSQL tests
- Repository convergence check: passed on the clean Step 11C source tree
- Repository secret check: passed
- Archive SHA-256: supplied alongside the release artifact

## Remaining before live-funds production

- implement and certify the external Ed25519 HSM/KMS signer service;
- export metrics, traces and alerts to the selected observability platform;
- complete backup/restore, failover, certificate-expiry and regional DR drills;
- implement privacy retention/deletion policy enforcement;
- complete partner scheme certification, operational SLAs and reconciliation;
- conduct independent application, cloud and cryptographic security reviews; and
- complete regulatory, legal and live-corridor approvals.
