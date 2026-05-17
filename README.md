# RailOne Protocol System (RPS)

## Deterministic Non-Custodial Cross‑Rail Execution Continuity Infrastructure

RailOne is a non-custodial bilateral execution coordination protocol designed to establish deterministic execution continuity across fragmented African financial rails.

Rather than acting as:

* a bank,
* a custodial wallet,
* a settlement network,
* or a mirrored_available_state-holding platform,

RailOne operates as:

* an execution continuity infrastructure layer,
* a bilateral orchestration protocol,
* a replay-safe transaction coordination engine,
* and a trust-oriented interoperability fabric.

The protocol is specifically optimized for:

* cross-border P2P transfers,
* wallet-to-bank execution,
* bank-to-wallet execution,
* wallet-to-wallet interoperability,
* and bank-to-bank coordination across heterogeneous African rails.

---

# Core Philosophy

## Continuity Over Isolated Execution

Traditional payment systems optimize for:

* routing,
* switching,
* settlement dispatch,
* or payment initiation.

RailOne instead optimizes for:

> deterministic execution continuity.

RailOne treats transactions not as isolated status records, but as:

* evolving continuity objects,
* replay-safe lineage systems,
* bilateral execution sessions,
* and canonical orchestration histories.

The protocol assumes fragmented financial rails are:

* asynchronous,
* operationally inconsistent,
* callback-fragmented,
* and occasionally adversarial.

Instead of assuming perfect execution, RailOne prioritizes:

* graceful failure handling,
* deterministic replay reconstruction,
* attributable execution lineage,
* canonical orchestration continuity,
* and operational explainability.

---

# Strategic Positioning

## RailOne IS NOT

RailOne is NOT:

* a custodial wallet,
* a ledger-centric fintech,
* a liquidity holder,
* a treasury institution,
* a neobank,
* or a traditional payment switch.

RailOne does NOT:

* custody user funds,
* maintain customer mirrored_available_states,
* replace settlement rails,
* own institutional liquidity,
* or perform omnibus custody.

Underlying funds remain within participating:

* banks,
* mobile money operators,
* PSPs,
* and institutional settlement rails.

---

# What RailOne Actually Is

RailOne is:

## A Deterministic Bilateral Execution Coordination Protocol

The protocol coordinates:

* bilateral execution participation,
* deterministic orchestration,
* replay-safe transaction continuity,
* execution provenance,
* institutional interoperability semantics,
* and cross-rail execution trust continuity.

RailOne sits:

* above fragmented rails,
* outside custody,
* and alongside institutions.

The protocol coordinates execution continuity without taking custody of value.

---

# High-Level Architecture

```text
+---------------------------------------------------+
|                RailOne Client Apps                |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|            Bilateral Session Layer                |
|     Consent • Participation • Attribution         |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|         Execution Coordination Engine             |
|  Replay Safety • Orchestration • Continuity       |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|       Institutional Integration Adapters          |
| Banks • Mobile Money • PSPs • Corridors           |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|              Settlement Infrastructure            |
+---------------------------------------------------+
```

---

# Current Protocol Architecture

## 1. Identity Continuity Layer

RailOne identity architecture is designed around:

> immutable continuity with bounded evolution.

### Components

| Component   | Purpose                                             |
| ----------- | --------------------------------------------------- |
| RIG         | Immutable identity genesis anchor                   |
| RIO         | Persistent institutional identity continuity object |
| RIV         | Bounded identity evolution state                    |
| Trust Tiers | Institution-readable trust classification           |
| ZK-SD       | Selective disclosure verification layer             |

### Canonical Identity Example

```text
R1-EA-T3-84F2A91
```

| Segment | Meaning               |
| ------- | --------------------- |
| R1      | RailOne namespace     |
| EA      | Corridor region       |
| T3      | Trust tier            |
| 84F2A91 | Continuity identifier |

### Current Prototype Status

Current implementation includes:

* identity generation,
* continuity identifiers,
* trust-oriented identity semantics,
* and attestation-aware identity progression.

Current prototype file:

```text
identity_engine.py
```

Example:

```python
return "R1-" + uuid.uuid4().hex[:10].upper()
```

Future architecture evolution includes:

* full RIG/RIO/RIV lineage,
* institutional attestation portability,
* replay-safe identity reconstruction,
* and privacy-preserving verification semantics.

---

# 2. Bilateral Execution Session Layer

RailOne introduces:

> bilateral execution participation.

Unlike traditional push-based systems where:

```text
Sender → Receiver
```

RailOne establishes:

```text
Sender ↔ Session ↔ Receiver
```

This creates:

* mutual participant awareness,
* deterministic consent lineage,
* execution attribution,
* and replay-safe orchestration context.

## Session Lifecycle

```text
SESSION_INITIATED
↓
PARTICIPANT_DISCOVERED
↓
RECEIVER_ATTESTED
↓
EXECUTION_INTENT_CREATED
↓
ETK-S_GENERATED
↓
ETK-R_DERIVED
↓
RTT_GENERATED
↓
ROUTE_COMPUTED
↓
EXECUTION_LOCKED
↓
EXECUTION_STARTED
↓
SETTLEMENT_CONFIRMED
↓
UTT_ISSUED
↓
FINALIZED
```

---

# 3. Execution Trust Architecture

RailOne introduces bounded execution authority using:

## Execution Trust Keys (ETKs)

### ETK-S

Sender execution authority.

### ETK-R

Receiver execution authority derived from:

* bilateral continuity,
* session lineage,
* and sender trust establishment.

These keys preserve:

* attributable execution,
* deterministic participation lineage,
* replay-safe ancestry,
* and bounded execution authority.

---

# 4. Route Trust Token (RTT)

The RTT is NOT merely a transaction reference.

The RTT represents:

> a canonical orchestration continuity object.

The RTT tracks:

* route continuity,
* execution progression,
* orchestration lineage,
* retry ancestry,
* replay reconstruction references,
* and corridor execution continuity.

Current prototype implementation includes:

* RTT verification,
* signature validation,
* and execution verification.

Example from current implementation:

```python
if not TokenFactory.verify(
    payload,
    signature,
    "R1CORE"
):
    raise Exception(
        "RTT_VERIFICATION_FAILED"
    )
```

---

# 5. Unified Transaction Token (UTT)

The UTT represents:

> canonical execution continuity proof.

The UTT persists across:

* retries,
* replay reconstruction,
* settlement coordination,
* compensating events,
* and execution recovery.

The UTT does NOT represent custody.

It represents:

* execution continuity,
* orchestration proof,
* settlement lineage,
* and replay-safe historical attribution.

Current implementation includes:

```python
utt = TokenFactory.generate_utt(
    "R1CORE"
)
```

---

# 6. Deterministic Execution Engine

The execution engine is responsible for:

* execution verification,
* continuity enforcement,
* attestation validation,
* replay-safe orchestration,
* and settlement progression.

Current prototype implementation includes:

* RTT verification,
* transaction verification,
* settlement finalization,
* event dispatching,
* and execution logging.

Prototype files:

```text
execution_engine.py
settlement_engine.py
execution_worker.py
execution_queue.py
failure_handler.py
```

---

# 7. Replay & Provenance Infrastructure

Replay reconstruction is foundational to RailOne.

The replay architecture attempts to preserve:

* canonical event continuity,
* settlement lineage integrity,
* deterministic historical reconstruction,
* and replay-safe execution ancestry.

## Canonical Replay Example

```text
Sender Debited
↓
Settlement Callback Missing
↓
Replay Checkpoints Loaded
↓
Canonical Lineage Validated
↓
Execution Continuity Reconstructed
↓
Authoritative State Determined
```

This architecture is one of RailOne’s primary strategic moats.

The long-term goal is to establish:

* authoritative replay continuity,
* deterministic interoperability semantics,
* and trusted execution provenance infrastructure.

---

# 8. Failure Semantics

RailOne assumes:

> fragmented execution environments are inherently asynchronous and imperfect.

The protocol explicitly models:

* delayed settlement,
* callback inconsistency,
* retry events,
* route degradation,
* settlement divergence,
* and reconciliation ambiguity.

## Canonical Failure States

```text
FAILED
REPLAY_REQUIRED
SETTLEMENT_DIVERGENCE
ROUTE_DEGRADED
EXECUTION_TIMEOUT
FRAUD_ESCALATION
RECONCILIATION_PENDING
```

RailOne prioritizes:

* graceful recovery,
* deterministic reconstruction,
* and attributable operational truth.

---

# Institutional Participation Model

RailOne is designed to coexist with institutions rather than replace them.

Participating institutions remain responsible for:

* custody,
* settlement,
* liquidity ownership,
* compliance,
* and account management.

RailOne coordinates:

* orchestration continuity,
* bilateral trust establishment,
* execution lineage,
* replay-safe reconstruction,
* and interoperability semantics.

## Institutional Benefits

RailOne attempts to reduce:

* reconciliation overhead,
* interoperability fragmentation,
* callback inconsistency,
* execution ambiguity,
* and operational uncertainty.

The architecture is intended to strengthen:

* execution confidence,
* transaction observability,
* deterministic replayability,
* and attributable settlement continuity.

---

# Current Prototype Components

## Current Modules

The prototype currently contains infrastructure modules for:

### Core Execution

* execution_engine.py
* execution_worker.py
* execution_queue.py
* settlement_engine.py
* failure_handler.py

### Identity & Trust

* identity_engine.py
* attestation_engine.py
* auth_engine.py
* auth_registry.py

### Routing & Corridor Infrastructure

* routing_engine.py
* corridor_fx_model.py
* corridor_pricing_engine.py
* fx_engine.py

### Institutional Integration

* bank_ke.py
* bank_tz.py
* bank_ug.py
* mpesa.py
* webhook_dispatcher.py

### Security & Compliance

* fraud_engine.py
* compliance.py
* audit.py
* tx_verifier.py

### Ledger Migration Note

Some prototype modules still contain legacy ledger-oriented implementation logic.

This is transitional.

RailOne architecture is actively evolving away from:

* custodial semantics,
* mirrored_available_state-centric infrastructure,
* and ledger-first execution design.

The long-term architecture direction prioritizes:

* orchestration continuity,
* bilateral execution sessions,
* provenance infrastructure,
* replay-safe coordination,
* and non-custodial institutional interoperability.

---

# African Interoperability Focus

RailOne is specifically optimized for fragmented African financial ecosystems where execution environments may involve:

* mobile money rails,
* bank APIs,
* PSP corridors,
* FX intermediaries,
* regional switches,
* payout systems,
* and heterogeneous settlement infrastructure.

The protocol intentionally prioritizes:

* rail coexistence,
* institutional compatibility,
* asynchronous execution resilience,
* and corridor-level adaptability.

---

# Security Priorities

RailOne assumes adversarial distributed execution environments.

Security priorities include:

* deterministic replay validation,
* immutable lineage,
* attributable execution continuity,
* revocation propagation,
* bounded authority,
* and canonical historical reconstruction.

Potential threat categories include:

* replay attacks,
* execution spoofing,
* route manipulation,
* duplicate execution,
* settlement divergence,
* and attestation compromise.

---

# Long-Term Vision

RailOne is evolving toward:

> a deterministic non-custodial cross‑rail execution continuity protocol for Africa.

The architecture combines:

* bilateral execution sessions,
* replay-safe transaction continuity,
* canonical execution provenance,
* attestation-driven orchestration,
* institutional trust portability,
* and deterministic interoperability semantics.

The long-term objective is to establish:

* institution-compatible interoperability,
* replay-safe execution continuity,
* deterministic orchestration infrastructure,
* and trusted cross-rail coordination across fragmented African financial ecosystems.

---

# Development Status

Current Status:

```text
Architecture Prototype / Infrastructure Draft
```

Current implementation is focused on:

* protocol semantics,
* execution continuity primitives,
* orchestration infrastructure,
* replay-safe lifecycle modeling,
* and institutional interoperability coordination.

The architecture is actively evolving.

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
