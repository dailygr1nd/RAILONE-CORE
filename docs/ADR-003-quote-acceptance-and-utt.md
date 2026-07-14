# ADR-003: Quote Acceptance and Immutable UTT Creation

- Status: Accepted
- Date: 2026-07-14
- Depends on: ADR-001 and ADR-002

## Decision

A RailOne quote is a signed, expiring commercial offer. It binds amounts,
currencies, customer-visible fee, internal routing budget, retry policy, service
level, corridor, participants, purpose, and pricing version. It does not promise
or expose a specific execution rail because RailOne sells execution finality and
may reroute after acceptance.

The UTT is created only after explicit acceptance of a cryptographically valid,
unexpired quote. Acceptance time is assigned by RailOne, not trusted from an
external caller.

Acceptance atomically persists:

- the immutable signed UTT;
- its signed ETK-S sender-authority attestation;
- the quote-to-UTT uniqueness record;
- the idempotency record.

The UTT owns commercial terms but not mutable execution state. Status, attempts,
provider responses, reconciliation, and settlement remain append-only execution
events and projections.

## Identifier semantics

The quote ID and UTT ID are deterministic content identifiers over canonical
contract material. Their integrity authority comes from the Ed25519 signature,
not from the identifier hash alone.

The idempotency key is never embedded in the public UTT. RailOne stores a hash
of the stable acceptance request and rejects reuse of the same key for different
material.

## Origin contexts

Supported pilot contexts are P2P, merchant, and partner. Merchant contexts must
carry `merchant_id` and may carry `branch_id`. Controlled purposes include P2P,
supplier payment, branch fund transfer, merchant-to-merchant payment, refund,
expense settlement, and generic bulk disbursement.

Payroll is not an Avia pilot capability and is not included in the current
purpose enumeration.

## Invariants

- Invalid, tampered, not-yet-valid, or expired quotes cannot create UTTs.
- One quote creates at most one UTT.
- One idempotency key plus the same request returns the original contract.
- One idempotency key plus different request material fails closed.
- ETK-S and UTT reference the same quote, payer, amount, currency, and UTT ID.
- Money uses integer minor units.
- Pricing is per intent.
- Custody model is always `NON_CUSTODIAL`.
- UTT payloads cannot be mutated after signing.
- ExecutionPlan and RTT creation must require a persisted UTT.
