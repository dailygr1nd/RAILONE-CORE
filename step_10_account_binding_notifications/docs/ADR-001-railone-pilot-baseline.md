# ADR-001: RailOne Pilot Architecture and Cryptographic Baseline

- Status: Accepted
- Date: 2026-07-14
- Scope: RailOne pilot convergence
- Supersedes: Any document or implementation that creates an RTT before a UTT,
  issues a UTT after settlement, charges per RTT attempt, or models RailOne as
  custodian of customer or merchant funds.

## Decision

RailOne is a non-custodial execution orchestration system with first-class P2P
capabilities. It consumes authorized movement intentions, creates a commercial
execution contract after quote acceptance, and routes execution requests into
external institutional rails.

The canonical order is:

1. An origin submits an execution intention.
2. RailOne validates identity, authority, compliance context, and idempotency.
3. RailOne issues a signed quote.
4. The origin explicitly accepts the unexpired quote.
5. RailOne creates one immutable UTT containing the accepted commercial terms.
6. RailOne persists an ExecutionPlan containing ranked route candidates and the
   retry budget.
7. RailOne creates an RTT for the selected route attempt.
8. The adapter submits the execution request to an external rail using a stable
   attempt idempotency key.
9. Provider callbacks and active queries are normalized into canonical events.
10. A failed route closes its RTT and may create another RTT under the same UTT.
11. Settlement is finalized only after verified provider evidence and
    reconciliation.

## UTT semantics

The UTT is the immutable commercial execution contract. It owns:

- accepted quote reference and quote snapshot hash;
- payer and beneficiary references;
- amount in integer minor units and currency;
- customer-visible fee and pricing model;
- maximum attempt policy;
- origin and purpose context;
- custody model `NON_CUSTODIAL`.

Mutable execution state is not stored inside the immutable UTT payload. Current
status is a projection derived from append-only events.

The customer is charged once per UTT. RTT replay, retry, and route mutation must
never generate another customer charge.

## ExecutionPlan and RTT semantics

An ExecutionPlan belongs to one UTT and preserves:

- original ranked routes;
- currently eligible routes;
- failed routes and failure classifications;
- route penalties and mutation history;
- attempts used and maximum attempts;
- successful route when finality is achieved.

Every RTT is an append-only execution attempt. An RTT contains its UTT reference,
attempt number, selected route, route score, selection reasons, previous route,
status, provider reference, failure reason, and replay lineage.

## Routing authority

The deterministic routing engine is the execution authority. Route scoring may
use latency, congestion, liquidity capacity, throughput threshold, speed, cost,
and link status. AI may recommend routes later, but it cannot authorize or
execute movement.

## Non-custodial boundary

RailOne must not:

- hold customer or merchant funds;
- expose a RailOne wallet or spendable balance;
- treat mirrored provider state as authoritative custody;
- mark settlement from an internal debit/credit operation;
- own the commercial workflow that created an intention.

RailOne may store observed external capacity, provider authorization references,
expected movements, execution reservations, reconciliation state, settlement
evidence, and accounting projections. These records describe execution; they do
not represent custody.

## P2P and Avia contexts

P2P remains a first-class origin context. Avia remains the Merchant OS and owns
merchant operational truth. Avia may submit merchant-context intentions such as
supplier payments, branch fund transfers, merchant-to-merchant payments,
refunds, expense settlements, and future generic bulk disbursements.

RailOne must not import Avia modules or encode Avia workflow logic. It receives a
generic origin envelope containing `origin_system`, `origin_intent_id`,
`context_type`, `merchant_id` where applicable, `branch_id` where applicable,
and a controlled purpose code.

Avia does not currently include payroll. The RailOne contract may remain capable
of receiving a future `PAYROLL_DISBURSEMENT` purpose without implementing
payroll business logic.

Identity fields remain typed: `continuity_uid` identifies a human continuity
subject, `merchant_id` a commercial entity, `partner_id` an institutional or PSP
partner, and `branch_id` a merchant operating unit. They must not be collapsed
into one identifier.

## Cryptographic baseline

Ed25519 is RailOne's canonical signature algorithm for quotes, UTTs, RTTs,
execution events, settlement evidence, identity attestations, and replay
checkpoints. It is a signature algorithm, not an encryption algorithm.

Cryptographic controls must include:

- canonical payload serialization;
- artifact-domain separation;
- signature versioning and algorithm agility;
- key identifiers and isolated key purposes;
- public-key registry with activation, expiry, rotation, and revocation;
- private keys held outside the application database and source repository;
- preservation of historical verification metadata;
- TLS 1.3 in transit and authenticated encryption for sensitive data at rest.

All private keys contained in the uploaded repository snapshot are considered
non-production and compromised for future trust purposes. They must be revoked,
removed from Git history, and replaced before pilot integration.

## Identity continuity

The current eight-hex-character random continuity identifier is rejected.
Production identity continuity requires at least 128 bits of collision-resistant
identifier space and a privacy-preserving deterministic recovery strategy. Raw
national identifiers must not be hashed without a secret institutional key or
stored as plaintext operational identifiers.

Institutional attestations must be verified cryptographically. Reconstructing a
plain SHA-256 string containing a public key is not signature verification.

## Pilot invariants

- No RTT exists without a persisted UTT.
- No ExecutionPlan exists without a persisted UTT.
- One accepted idempotency key cannot create two UTTs.
- Commercial UTT fields cannot be updated after creation.
- An RTT belongs to exactly one UTT.
- Provider submission is idempotent per RTT attempt.
- Unknown provider outcomes enter reconciliation; they are never retried blindly.
- Settlement requires provider evidence and reconciliation.
- Revenue is recognized once, at the UTT level, according to the accepted price.
- Money is represented using integer minor units or fixed precision, never float.
- State change, event append, and outbox enqueue are committed atomically.
- Redis coordinates work but is never the authoritative execution history.

## Implementation sequence

1. Cryptographic contracts and key lifecycle.
2. Quote acceptance and immutable UTT.
3. Persisted ExecutionPlan and RTT attempt model.
4. Transactional event store and outbox.
5. Durable worker lease and execution runner.
6. One complete provider adapter and webhook reconciliation path.
7. P2P and generic merchant-context intent API.
8. Identity continuity hardening.
9. Operational readiness, observability, recovery drills, and pilot gates.
