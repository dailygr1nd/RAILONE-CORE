# ADR-010: Partner account binding and settlement notifications

- Status: Accepted for the controlled pilot baseline
- Date: July 14, 2026
- Scope: Partner institution selection, UTT endpoints, settlement SMS

## Decision

Onboarding creates reusable bindings between an actor, a participating
institution, and an institution-attested account. Each execution intention
selects one sender `DEBIT` binding and one receiver `CREDIT` binding. Quote
issuance validates both bindings against the active partner directory. Quote
acceptance places an immutable endpoint snapshot in the UTT.

The endpoint snapshot contains the institution identity and display name, an
opaque account-binding ID, account role/type, a masked display hint, an opaque
contact binding, and an attestation reference. It never contains the provider-
ready account number, card number, wallet identifier, or MSISDN.

Provider endpoints are resolved from opaque binding IDs at dispatch through an
isolated resolver boundary. The included in-memory resolver is test-only;
production must use an encrypted token vault or equivalent isolated service.

## Routing invariant

The UTT endpoint institutions are fixed. Route candidates are eligible only
when their source and destination institutions match the UTT. Intermediaries,
rails, and RTT attempts may change. Endpoints may not. Every new RTT revalidates
that both partner institutions and account bindings remain active without
rewriting the signed UTT.

Step 10 marks the endpoint schema as `endpoint_model_version=1`. Step 09 UTTs
without this model fail closed at RTT creation. Because RailOne is pre-pilot,
they must be replaced through a new quote and acceptance rather than silently
rewritten.

## Settlement evidence

An M-PESA success callback first passes ingress authentication, provider
reference correlation, amount matching, transaction-ID validation, and RTT
finalization. RailOne then creates an Ed25519-signed
`railone.settlement_evidence` artifact with the UTT/RTT lineage and provider
transaction reference.

The settlement evidence ID is derived from stable callback and transaction
identity, not callback processing time. A crash and later callback retry
therefore returns the original evidence and notifications.

## SMS notification semantics

Exactly one sender and one receiver SMS record are committed with settlement
evidence. A settlement SMS is prohibited for `ACCEPTED_FOR_PROCESSING`, timeout,
unknown outcome, or `RECONCILIATION_REQUIRED`.

The outbox stores an opaque contact binding and a privacy-safe rendered body;
it never stores a destination phone number. Delivery follows
`PREPARED -> DISPATCHING -> SENT|REJECTED|UNKNOWN`. A worker restart from
`DISPATCHING` resolves to `UNKNOWN` without another provider call unless a
future SMS adapter supplies a verifiable idempotency contract.

Sender template:

```text
RailOne: SETTLED. {send_currency} {send_amount} sent to {receiver_display} via {destination_institution} on {settled_at_local}. Ref {utt_short}. Fee {fee_currency} {fee_amount}.
```

Receiver template:

```text
RailOne: SETTLED. You received {receive_currency} {receive_amount} from {sender_display} into {destination_institution} {credit_account_hint} on {settled_at_local}. Ref {utt_short}.
```

The UTT—not an RTT—is the customer reference. Full accounts, phone numbers,
ContUIDs, national identifiers, binding IDs, authorization references, and
internal routing costs are forbidden from SMS bodies.

## Persistence

Migration 0006 adds durable partner institutions, opaque account bindings,
signed settlement evidence, and the SMS outbox. Database triggers protect
binding identity, append-only evidence, notification birth material, versions,
and delivery state transitions.

## Remaining gates

- production account/contact token vault;
- actual institution onboarding and consent APIs;
- selected SMS provider adapter and sender-ID registration;
- country-specific communications/privacy review;
- live PostgreSQL upgrade and concurrency tests;
- callback-to-settlement crash/replay drills; and
- SMS delivery receipts, monitoring, rate limits, and suppression policy.
