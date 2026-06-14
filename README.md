Good point. Before rewriting code, I'd write a design paper that becomes the authoritative specification for RailOne's execution model. Otherwise you'll end up rewriting files twice.

---

# RailOne Execution Architecture

## UTT-Driven Intelligent Routing with Replayable Execution

### Version

Draft 1.0

### Status

Architectural Proposal

---

# 1. Purpose

This document defines how RailOne executes payment intents across multiple financial rails while maintaining:

* Deterministic execution
* Intelligent routing
* Replayability
* Auditability
* Commercial consistency

The architecture separates:

1. Commercial Intent
2. Routing Decisions
3. Execution State
4. Revenue Recognition

into distinct components.

---

# 2. Core Principle

RailOne does not sell access to rails.

RailOne sells:

> Execution Finality

A customer does not purchase:

* SWIFT
* RTGS
* Pesalink
* Bilateral Networks

A customer purchases:

> Transfer value from Institution A to Institution B.

Routing is an internal concern of RailOne.

---

# 3. Network Model

RailOne models the payment ecosystem as a graph.

## Nodes

Nodes represent institutions.

Examples:

```text
KCB
ABSA
CRDB
NMB
Equity
Stanbic
```

---

## Edges

Edges represent rails.

Examples:

```text
Pesalink
SWIFT
RTGS
TIPS
Bilateral Network
Payment Orchestrator
```

---

Example:

```text
KCB
 │
 ├── Pesalink ── ABSA
 │
 ├── SWIFT ───── ABSA
 │
 ├── RTGS ────── ABSA
 │
 └── Bilateral ─ ABSA
```

Multiple edges may connect the same node pair.

---

# 4. Routing Philosophy

There is rarely only one path through which value can move.

Therefore RailOne evaluates all available rails before execution.

The objective is:

```text
Find the best available route
at the time of execution.
```

---

# 5. Route Scoring

Every route receives a dynamic score.

Example:

```python
score = f(

    latency,

    congestion,

    liquidity_capacity,

    throughput_threshold,

    speed,

    cost,

    link_status

)
```

---

## Routing Factors

### Latency

Response time of the rail.

---

### Congestion

Current traffic level.

---

### Liquidity Capacity

Available liquidity.

---

### Throughput Threshold

Maximum sustainable volume.

---

### Speed

Settlement performance.

---

### Cost

Execution cost.

---

### Link Status

Health and availability.

---

# 6. AI-Assisted Routing

Artificial Intelligence does not execute payments.

AI assists route discovery.

---

## AI Responsibilities

```text
Analyze rails
Detect patterns
Predict failures
Suggest routes
```

---

## Engine Responsibilities

```text
Score routes
Select routes
Execute routes
Manage retries
Finalize execution
```

Decision authority remains with the routing engine.

---

# 7. UTT: Universal Transaction Token

## Definition

UTT represents execution intent.

It is generated immediately after quote acceptance.

---

## Why UTT Exists

Before execution begins:

```text
Amount
Currency
Participants
Pricing
Validity
```

must be frozen.

UTT becomes the authoritative contract for execution.

---

## UTT Responsibilities

```text
Bind execution intent
Store commercial terms
Define retry policy
Anchor execution history
Enable auditability
```

---

## Example

```json
{
  "utt_id": "UTT-001",

  "quote_id": "Q-001",

  "amount": 1000,

  "currency": "USD",

  "routing_fee": 3.00,

  "pricing_model": "PER_INTENT",

  "max_retry_attempts": 5,

  "status": "PROCESSING"
}
```

---

# 8. Why RTT Must Come After UTT

RTTs represent execution attempts.

Execution attempts cannot exist without execution intent.

Therefore:

```text
Quote Accepted
        ↓
UTT Created
        ↓
RTT Created
```

Never:

```text
Quote Accepted
        ↓
RTT Created
        ↓
UTT Created
```

because RTT would have no authoritative execution context.

---

# 9. RTT: Routing Transaction Token

## Definition

RTT represents routing state.

It is generated after UTT creation.

RTTs may mutate throughout execution.

---

## RTT Responsibilities

```text
Track route selection
Track failures
Track retries
Track route changes
Track execution status
Provide replayability
```

---

## Example

```json
{
  "rtt_id": "RTT-001",

  "utt_id": "UTT-001",

  "attempt": 1,

  "selected_route": "Pesalink",

  "status": "FAILED",

  "failure_reason": "INSUFFICIENT_LIQUIDITY"
}
```

---

# 10. Replay Capability

Every RTT is preserved.

Example:

```text
UTT-001

RTT-001
FAILED

RTT-002
FAILED

RTT-003
SUCCESS
```

Execution history can be reconstructed at any time.

---

# 11. Retry Architecture

RailOne optimizes for finality.

Failure of a route does not imply failure of intent.

---

Example:

```text
Attempt 1
Pesalink
FAILED

Attempt 2
RTGS
FAILED

Attempt 3
SWIFT
SUCCESS
```

Intent reaches finality.

---

# 12. Commercial Model

## Per-Intent Pricing

Customers are charged once.

Example:

```text
KCB → ABSA

Fee = $3
```

Customer purchased:

```text
Execution Outcome
```

not:

```text
Specific Route
```

---

# 13. Why Per-Attempt Charging Is Rejected

Bad model:

```text
Attempt 1 = $3

Attempt 2 = $3

Attempt 3 = $3
```

Total:

```text
$9
```

This creates:

* unpredictable costs
* customer dissatisfaction
* poor scalability

---

# 14. Routing Budget

UTT may contain an internal routing budget.

Example:

```json
{
  "routing_fee": 3.00,

  "routing_budget": 1.20
}
```

This budget absorbs retries and failovers.

---

# 15. Revenue Recognition

Revenue is not recognized when RTTs are created.

Revenue is recognized when execution reaches finality.

---

Example:

```text
UTT FINALIZED
        ↓
Revenue Event
```

---

# 16. State Machine

```text
QUOTE_ACCEPTED

↓
UTT_CREATED

↓
PROCESSING

↓
RTT_CREATED

↓
EXECUTING

↓
RETRYING

↓
FINALIZED
```

or

```text
FAILED
```

---

# 17. Design Summary

RailOne is fundamentally:

```text
UTT
=
Commercial Contract

RTT
=
Execution Evidence

Routing Engine
=
Decision System

AI
=
Advisory Layer

Ledger
=
Financial Truth
```

The objective of the platform is not to execute through a specific rail.

The objective is to drive every valid execution intent toward a finalized state while preserving full replayability, auditability, and routing intelligence.

---

Now, for the code rewrite, paste these files first:

1. Your current `UTT` generation file.
2. Your current `RTT` generation file.
3. Your `EventType` enum.
4. Any execution/orchestration file that currently creates RTTs.

Once I see those, I'll help you refactor them into a proper **UTT-parent / RTT-child execution architecture** instead of just patching the current implementation.


---

# Closing Statement

RailOne is not attempting to replace financial institutions.

Instead, the protocol attempts to solve one of the hardest operational problems in fragmented financial ecosystems:

> deterministic execution continuity.

By combining:

* bilateral execution participation,
* replay-safe orchestration,
* canonical lineage,
* and institution-compatible interoperability,

RailOne aims to establish a new trust-oriented coordination model for African financial execution environments.

---

# Avia Technologies

Engineering Trust Infrastructure
