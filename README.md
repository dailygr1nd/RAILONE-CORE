

# 🧠 RailOne Core Cryptographic & Transaction Terminology

## 🔐 Ephemeral & Transaction Identity Layer

RailOne uses a multi-stage token system to model secure, idempotent, and verifiable financial transactions across distributed rails.

All tokens are:

* **Ephemeral**
* **Idempotent**
* Represented as **128-bit cryptographic values**
* Stored and transmitted as **hashed (display-safe) strings**

---

# 🧩 1. ETK-S — Ephemeral Transaction Key (Sender Lock)

### Definition

The **ETK-S** is generated at the point of transaction initiation by the sender.

### Purpose

* Locks **sender intent**
* Prevents duplicate submission (idempotency guard)
* Acts as the first half of the transaction handshake

### Properties

* Generated at sender initiation
* Time-bound / ephemeral
* Bound to:

  * sender identity token
  * transaction payload
  * timestamp

### Output

* 128-bit key (hashed representation)

---

# 🧩 2. ETK-R — Ephemeral Transaction Key (Receiver Lock)

### Definition

The **ETK-R** is generated after receiver-side validation and confirmation.

### Purpose

* Locks **receiver acceptance**
* Completes the transaction handshake model
* Acts as a cryptographic derivative of ETK-S

### Relationship

> ETK-R is a **deterministic derivative of ETK-S**

This ensures:

* Transaction integrity continuity
* Non-repudiation between sender and receiver states

### Properties

* Derived, not independently random
* Bound to:

  * ETK-S
  * receiver identity token
  * acceptance state

---

# 🔗 3. RTT — RailOne Tracking Token

### Definition

The **RTT (RailOne Tracking Token)** is the final **handshake verification token**.

### Purpose

* Confirms full transaction handshake completion
* Verifies integrity between ETK-S and ETK-R
* Serves as system-level transaction trace key

### Generation Logic

```
RTT = HASH(ETK-S + ETK-R + transaction_context)
```

### Properties

* Finalized after both sender + receiver locks exist
* Used for:

  * routing validation
  * ledger anchoring
  * audit verification

---

# 🧾 4. UTT — Unique Transaction Token

### Definition

The **UTT (Unique Transaction Token)** is the **global system-level transaction identifier**.

### Purpose

* Acts as the **primary transaction ID across RailOne**
* Ensures global uniqueness of all processed transactions
* Links RailOne processing events across services

### Institutional Role

The UTT also embeds:

* Institution identifier (RailOne participant / bank / rail node)
* Transaction metadata context

### Format Standard

UTT is structured in an **ISO-style transaction format**:

```
UTT-{INSTITUTION_ID}-{TIMESTAMP}-{HASH_SUFFIX}
```

Example:

```
UTT-R1BANK-20260413T142355Z-A9F3C2B1
```

---

# 🧾 Transaction Object Embedding Standard

Every RailOne transaction object contains:

### Required Fields:

* UTT (global transaction ID)
* RTT (handshake verification token)
* ETK-S (sender intent lock)
* ETK-R (receiver confirmation lock)
* timestamp (ISO 8601 format)
* sender_id
* receiver_id
* amount
* currency
* status

---

# ⏱️ ISO 8601 Time Standard

All RailOne timestamps MUST follow:

```
YYYY-MM-DDTHH:MM:SSZ
```

Example:

```
2026-04-13T14:23:55Z
```

---

# 🔄 Transaction Lifecycle (Cryptographic Flow)

```
1. ETK-S generated (Sender locks intent)
        ↓
2. Transaction routed / held
        ↓
3. Receiver validates → ETK-R generated
        ↓
4. RTT computed (handshake validation)
        ↓
5. UTT assigned (global system ID)
        ↓
6. Ledger commit + audit entry
```

---

# 🧠 Design Principles

RailOne transaction security model is built on:

### 1. Idempotency

* No transaction can be duplicated or replayed

### 2. Ephemerality

* ETK-S and ETK-R expire after transaction completion window

### 3. Cryptographic Traceability

* RTT ensures full handshake integrity

### 4. System-wide Uniqueness

* UTT guarantees global transaction identity across all rails

### 5. Institutional Awareness

* UTT embeds institution-level routing metadata

---

# 🏦 Architectural Role in RailOne

These tokens sit at the **core of RailOne’s transaction engine**:

```
Identity Layer → ETK-S generation
Routing Layer  → ETK-R confirmation
Core Engine    → RTT computation
System Layer   → UTT assignment
Ledger Layer   → Immutable recording
```

---

# 🚀 Why this matters (engineering view)

This system gives RailOne:

* Bank-grade auditability
* Multi-rail reconciliation capability
* Strong anti-replay protection
* Deterministic transaction tracing
* Cross-institution compatibility layer

---

# 📌 Next Step (important)

Now that your cryptographic model is defined, the *next engineering step* is:

## 🔥 Build the Transaction Engine State Machine

We implement:

```
INIT → ETK-S → ROUTING → ETK-R → RTT → UTT → SETTLED / FAILED
```

with:

* locking system
* rollback logic
* ledger append-only integrity

---


