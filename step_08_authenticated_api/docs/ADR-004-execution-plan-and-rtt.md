# ADR-004: Deterministic Execution Plans and RTT Attempts

- Status: Accepted for pilot baseline
- Date: 2026-07-14
- Owners: RailOne core execution team
- Supersedes: legacy route selection and mutable transfer-attempt behavior

## Context

RailOne is a non-custodial execution orchestrator. It accepts an authorized
commercial intention as a signed UTT and routes that intention to external
rails. P2P is a first-class origin. Avia participates only through generic
merchant contexts such as supplier payment and branch fund-transfer intents;
Avia retains ownership of its merchant workflows.

One commercial intention may require several provider attempts. Those retries
must never create a second customer charge, lose the original authorization
lineage, or submit a duplicate payment after an ambiguous provider response.

## Decision

### Execution order

The pilot execution order is:

1. Verify and load a persisted signed UTT.
2. Construct one immutable `ExecutionPlan` for that UTT.
3. Filter ineligible routes before scoring.
4. Rank eligible routes with deterministic integer arithmetic.
5. Create and Ed25519-sign one immutable RTT birth artifact per attempt.
6. Record attempt outcomes separately from the signed birth artifact.
7. Retry only after an explicit, retryable failure.
8. Finalize, fail, exhaust, or hold for reconciliation.

An unknown UTT cannot create an execution plan or RTT. The persistence adapter
must enforce the UTT foreign-key relationship and one plan per UTT.

### Route eligibility

A route is ineligible if any of these conditions is true:

- its link is `DOWN`;
- telemetry is not yet observable or has expired;
- source or destination currency differs from the UTT;
- the UTT amount is outside route bounds;
- available liquidity is lower than the UTT amount; or
- estimated route cost exceeds the remaining routing budget.

Route identifiers must be unique within a planning request.

### Deterministic ranking

All financial values use integer minor units. All normalized metrics and
weights use basis points from 0 to 10,000. Floating-point arithmetic is
forbidden. The pilot weights are:

| Signal | Weight (bps) |
|---|---:|
| Latency | 1,600 |
| Congestion | 1,200 |
| Liquidity | 1,700 |
| Throughput headroom | 1,200 |
| Speed | 1,200 |
| Cost | 1,800 |
| Link status | 1,300 |
| Total | 10,000 |

The scorer sorts by descending composite score and then ascending route ID.
This stable tie-break makes the same inputs produce the same ordering. A later
AI advisory layer may propose signals or policies, but only this deterministic
policy boundary may authorize an execution route.

### RTT semantics

Each RTT is an Ed25519-signed immutable birth artifact. It includes:

- its UTT and ExecutionPlan identifiers;
- the hash of the signed UTT payload;
- attempt number and replay generation;
- a complete route snapshot and score components;
- previous RTT and route identifiers for retry lineage;
- creation time, `CREATED` birth state, and `NON_CUSTODIAL` custody model.

Operational attempt state is stored in an attempt record and evolves from
`CREATED` to one of `FAILED`, `SUCCEEDED`, or
`RECONCILIATION_REQUIRED`. The signed RTT is never rewritten.

RTTs contain no customer fee. Customer pricing remains `PER_INTENT` on the UTT,
so RailOne charges once per UTT and never once per RTT.

### Failure policy

Failures have one of three explicit dispositions:

- `RETRYABLE`: close the current attempt and consider the next affordable
  route, subject to the UTT attempt cap.
- `TERMINAL`: fail the ExecutionPlan and do not submit another route.
- `RECONCILIATION_REQUIRED`: retain the ambiguous attempt as current, block all
  retries, and wait for provider evidence or an operator-controlled resolution.

Timeout-after-submit and any other unknown provider outcome must be classified
as `RECONCILIATION_REQUIRED`. Treating an unknown outcome as retryable could
produce a duplicate payment.

### Persistence and concurrency

ExecutionPlan updates use compare-and-swap versions. Starting an RTT and
updating its plan are one atomic transaction. Recording an outcome and updating
the plan are also one atomic transaction. The in-memory adapter is test-only;
production must implement the same rules in a durable transactional database.
Redis may cache derived data but is never authoritative.

## Consequences

- Execution behavior is replayable and auditable from fixed inputs.
- Route retry cannot silently escape the original accepted commercial intent.
- Ambiguous provider responses prioritize duplicate-payment prevention over
  availability.
- Provider adapters must return normalized outcome codes and dispositions.
- Settlement evidence, signed execution events, durable SQL migrations,
  reconciliation release, and operator controls remain later pilot steps.
