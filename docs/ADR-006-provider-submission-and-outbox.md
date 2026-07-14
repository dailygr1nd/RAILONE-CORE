# ADR-006: Provider Submission and Signed Transactional Outbox

- Status: Accepted for pilot baseline
- Date: 2026-07-14
- Depends on: ADR-003, ADR-004, ADR-005

## Current

Step 05 established signed UTTs, deterministic ExecutionPlans, signed RTT birth
artifacts, identity continuity, and durable schema contracts. Direct provider
submission was still undefined. A naive worker could therefore resubmit after
a timeout or process crash and create a duplicate payment.

## Decision

Every provider submission is prepared from one current, signed RTT and its
persisted signed UTT. RailOne derives a stable provider idempotency key from the
provider and RTT. The request hash includes the complete provider execution
request, while signed operational events omit payer and beneficiary account
references.

A provider submission moves through:

`PREPARED → DISPATCHING → ACCEPTED | REJECTED | UNKNOWN`

- `ACCEPTED` means only that the provider accepted the request for processing.
  It does not mean settlement succeeded and must not finalize the UTT.
- `REJECTED` is a known non-execution response and requires an explicit
  `RETRYABLE` or `TERMINAL` disposition.
- `UNKNOWN` means RailOne cannot prove whether execution occurred. Network
  exceptions after entering an adapter are classified as `UNKNOWN`; they are
  never treated as ordinary retryable failures.

Final provider-submission records are idempotent. Calling dispatch again does
not call the provider again. Crash recovery from `DISPATCHING` may resubmit only
when the provider contract guarantees idempotency with the same key. Otherwise
the outcome must become `UNKNOWN` and enter reconciliation.

Each operational transition creates an Ed25519-signed execution event in the
same authoritative transaction as the state change. The outbox relay is
at-least-once: workers claim events with leases, publish the immutable signed
event, and mark delivery. Expired leases may be reclaimed. Consumers must
deduplicate by `event_id`.

Redis or a message broker transports events but is not the authoritative
outbox, provider-submission record, RTT, or UTT store.

## Interpretation

The domain implementation now proves stable request idempotency, final-state
dispatch suppression, conservative unknown-outcome handling, signed event
generation, and lease-safe outbox retries. The included SQL migration defines
the durable tables and constraints.

This does not yet prove the PostgreSQL adapter, message broker, or a real
provider sandbox. Those require integration and failure testing.

## Roadmap

The next implementation must connect these contracts to PostgreSQL, apply
provider outcome events to RTT and ExecutionPlan state exactly once, open
reconciliation cases for unknown outcomes, and expose authenticated APIs.
