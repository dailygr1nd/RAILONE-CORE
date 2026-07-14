# Step 11B release manifest

- Build date: July 14, 2026
- Package version: 0.12.0
- Custody model: non-custodial
- Signature baseline: Ed25519
- At-rest confidentiality: versioned AES-256-GCM envelope encryption
- Effect model: deterministic synthetic `BANK-KE` and `MPESA-KE`
- Migration chain: immutable `0001` through `0007`
- Runtime restriction: `SIMULATED_PILOT`

## Added controls

- purpose-separated per-record AES-256-GCM envelopes;
- canonical associated data bound to record, owner, purpose, and field;
- wrapped DEKs and an isolated KMS/HSM client boundary;
- encrypted account-endpoint and contact-destination resolvers;
- append-only PostgreSQL encrypted-secret persistence;
- deterministic accepted, rejected, unknown, timeout, and settlement effects;
- refusal of non-synthetic provider endpoint references;
- pilot readiness and metric surfaces; and
- Step 11B ADR and sandbox runbook.

## Verification result

- Tests discovered: 123
- Runnable tests passed locally: 116
- Environment-gated tests skipped locally: 7
- Repository convergence check: passed on the clean Step 11B source tree
- Repository secret check: passed
- Archive SHA-256: supplied alongside the release artifact

## Still blocked before live-funds production

- partner certification and contractual scheme access;
- deployed KMS/HSM and signing-service implementations;
- encrypted provider-credential and notification-body store integration;
- full worker supervision, durable effect scheduling, telemetry export, and
  disaster-recovery exercises;
- privacy retention/deletion controls and independent security review; and
- live corridor, liquidity, settlement, and reconciliation certification.
