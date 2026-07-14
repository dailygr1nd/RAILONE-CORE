# ADR-012: Deployable Sandbox Persistence and Workers

- Status: Accepted
- Date: 2026-07-14
- Scope: RailOne Step 11C simulated pilot

## Context

Step 11B introduced encrypted endpoint/contact vaults and deterministic provider
effects. Its local queue and plaintext-compatible notification store were not a
shared-sandbox deployment profile. A process crash could lose an effect, and
provider credentials or rendered SMS bodies could still be persisted without
an enforced envelope boundary.

## Decision

Step 11C adopts these controls:

1. New PostgreSQL SMS records persist `[ENCRYPTED]` plus a versioned
   `NOTIFICATION_BODY` AES-256-GCM envelope. The delivery relay decrypts only
   after loading the record and verifies its body fingerprint.
2. M-PESA credentials resolve through the `PROVIDER_CREDENTIAL` encrypted vault.
   Deployed composition fails if notification encryption is absent.
3. Synthetic provider effects are durable PostgreSQL records with a persisted
   logical clock, delivery state, attempt count, lease owner, lease expiry,
   retry availability, and dead-letter outcome.
4. Workers use bounded `run_once` cycles. Claims use `FOR UPDATE SKIP LOCKED`;
   expired leases are reclaimable and stale workers cannot acknowledge them.
5. A supervisor reports repeated top-level worker failures without owning the
   operating-system process loop.
6. The deployed composition requires PostgreSQL, four purpose-specific KEK ids,
   an isolated key-service client and an effect consumer. It never creates or
   loads signing private keys.
7. Readiness requires migration `0008`, PostgreSQL availability, simulation-only
   mode, the isolated encryption boundary and a non-stopped worker.

## Preserved invariants

- Ed25519 signs artifacts; AES-256-GCM encrypts persisted sensitive values.
- Quote acceptance creates the immutable UTT before any RTT.
- The ExecutionPlan owns route mutation; each retry receives a new RTT.
- Unknown provider outcomes block blind resubmission.
- Provider acceptance is not settlement.
- P2P remains first-class, while Avia enters via merchant/branch/partner scopes.
- RailOne remains non-custodial and never holds customer or merchant funds.

## Consequences

- Existing plaintext-compatible SMS rows remain readable for migration safety,
  but the Step 11C deployed composition always writes encrypted bodies.
- A dead-letter effect requires operator reconciliation; it cannot silently
  disappear or be recreated with a new identity.
- The logical clock is a deterministic simulation mechanism, not a replacement
  for production provider timestamps.
- Production still requires the isolated Ed25519 signer, observability export,
  disaster-recovery drills, and partner certification.
