# 🏦 RailOne — Transaction Orchestration & Settlement Engine

RailOne is a **cryptographically verifiable, quote-bound transaction engine** designed for cross-rail financial interoperability.

It enables secure, deterministic, and auditable transaction execution across distributed financial systems (banks, PSPs, wallets) using a multi-stage token protocol.

---

# 🚀 Core Capabilities

### 🔐 Cryptographic Transaction Integrity

* Multi-stage token handshake (ETK-S → ETK-R → RTT)
* RSA-based signing and verification
* Trust registry with key rotation support
* Replay protection and idempotency enforcement

### 💱 Quote-Bound Execution

* Transactions are **locked to signed quotes**
* Pricing and routing cannot be altered post-initiation
* Expiry and replay protection enforced at protocol level

### 🔗 Deterministic Routing & Pricing

* Multi-hop routing support
* Liquidity-aware execution
* Tiered pricing + FX spread + routing premium
* Route integrity hashing

### ⚙️ Execution Safety

* Pre-execution verification (hard gate)
* Post-execution verification (audit guarantee)
* Automatic rollback + fund release on failure
* Dead-letter queue for invalid transactions

### 🧾 Full Auditability

* Cryptographic traceability via RTT
* Final settlement identity via UTT
* Verification hashing for audit trails
* Structured event logging

---

# 🧠 Architecture Overview

```
Identity Layer → ETK-S (Sender Intent Lock)
Routing Layer  → ETK-R (Receiver Confirmation)
Core Engine    → RTT (Transaction Binding)
Execution Layer → Ledger + UTT Assignment
Audit Layer     → Verification + Logging
```

---

# 🔑 Token Model

## 1. ETK-S (Ephemeral Transaction Key — Sender)

* Locks sender intent
* Prevents duplicate submission
* Time-bound + signed

## 2. ETK-R (Receiver Confirmation)

* Derived from ETK-S
* Confirms receiver acceptance
* Ensures continuity of transaction state

## 3. RTT (RailOne Tracking Token)

* Final handshake token
* Binds:

  * ETK-S
  * ETK-R
  * Transaction ID
  * Pricing
  * Quote ID

```
RTT = HASH(ETK-S + ETK-R + TX_ID + PRICING_HASH + QUOTE_ID)
```

* Signed by institution (R1CORE)
* Used for:

  * execution authorization
  * audit verification
  * route integrity validation

## 4. UTT (Unique Transaction Token)

* Assigned during execution
* Global transaction identity

```
UTT-{INSTITUTION}-{TIMESTAMP}-{SUFFIX}
```

---

# 🔄 Transaction Lifecycle

```
1. HANDSHAKE
   → ETK-S generated
   → ETK-R derived

2. QUOTE
   → Route + pricing computed
   → Signed + expiry enforced

3. TRANSACTION INIT
   → Quote verified
   → RTT generated (binding layer)
   → Funds locked

4. EXECUTION
   → RTT verified (hard gate)
   → Ledger applied
   → UTT assigned

5. FINALIZATION
   → Revenue extracted
   → Treasury rebalanced
   → Transaction settled
```

---

# 🔐 Security Model

### 1. Idempotency

* ETK-S prevents duplicate transactions
* Redis-backed replay protection

### 2. Ephemerality

* Tokens expire within defined TTL
* Quotes expire before execution

### 3. Cryptographic Verification

* All critical payloads are signed
* Multi-key verification via TrustRegistry

### 4. Economic Integrity

* Pricing hash embedded in RTT
* Quote binding prevents tampering

### 5. Execution Gating

* No transaction executes without passing verification

---

# ⚙️ Key Components

| Component            | Role                               |
| -------------------- | ---------------------------------- |
| `transaction_engine` | Orchestrates transaction lifecycle |
| `handshake_engine`   | Generates ETK-S + ETK-R            |
| `token_factory`      | Token creation + signing           |
| `tx_verifier`        | Cryptographic validation           |
| `execution_worker`   | Settlement engine                  |
| `execution_engine`   | Ledger application                 |
| `quote_engine`       | Route + pricing generation         |
| `trust_registry`     | Key lifecycle management           |
| `key_manager`        | Private key storage (HSM-ready)    |
| `revenue_engine`     | Revenue extraction                 |
| `treasury_engine`    | Liquidity rebalancing              |

---

# 📊 Revenue Model

RailOne captures value through:

* Base transaction fees (tiered)
* FX spread (cross-border)
* Routing intelligence premium

Revenue is:

* computed at quote stage
* enforced via RTT binding
* extracted post-settlement

---

# 🧪 Simulation Environment

The system includes:

* CLI transaction simulator
* Multi-institution mock network
* Mirror accounts with liquidity
* Redis-backed queues
* SQLite/Postgres ledger support

---

# 🧱 Production Readiness

RailOne is architected to support:

* HSM-backed key storage
* API-based institution integration
* Real-time settlement rails
* Horizontal scaling via workers
* Regulatory audit requirements

---

# ⚠️ Current Status

**Near-MVP (Protocol Complete)**

✔ Cryptographic transaction model
✔ Deterministic routing & pricing
✔ Execution safety + rollback
✔ Audit-grade verification

Remaining for full production:

* API gateway hardening
* Rate limiting + auth enforcement
* External rail integrations
* Monitoring + observability
* Persistent HSM integration

---

# 🧭 Design Philosophy

RailOne treats transactions as:

> **Verifiable state transitions, not mutable database events**

Every transaction is:

* cryptographically bound
* economically deterministic
* auditable end-to-end

---

# 🏁 Conclusion

RailOne is not just a payment system.

It is a **transaction protocol** designed for:

* interoperability
* trust minimization
* institutional-grade execution

---

# 📌 Next Steps

* Integrate real PSP/bank APIs
* Deploy HSM-backed key infrastructure
* Add API authentication + rate limiting
* Introduce monitoring (Prometheus/Grafana)
* Expand multi-currency liquidity engine

---

**RailOne — Building the rails behind the rails.**
