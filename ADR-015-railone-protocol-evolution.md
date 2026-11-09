# ADR-015 — RailOne Protocol Evolution: Granular Fencing, Canonical Adapter Envelopes and Institutional Licensing

- **Status:** PROPOSED — architecture review; not approved or implemented
- **Date:** 2026-11-04
- **Owner:** RailOne Architecture & Assurance
- **Scope:** RailOne Core, institution adapters, partner SDK, conformance and commercial entitlement control plane
- **Supersedes:** Nothing automatically. Extends ADR-004, ADR-013, ADR-014 and proposes controlled revisions to RO-DOC-RTT-006, RO-DOC-ARCH-002 and the institution-adapter specifications.
- **Basis:** Supplied RailOne repository snapshot, July 2026 controlled specifications, October 29 granular-fencing extension, concurrency/indexing strategy and sample wrapper. All new designs below are **proposals**, not statements of implementation.

## 1. Context and objective

RailOne is a non-custodial, P2P-first orchestration and routing fabric. It creates one immutable UTT from an accepted quote, persists an ExecutionPlan and governs signed RTT attempts through exact-version institution adapters. Providers—not RailOne—hold and settle funds. AviaOS is a separate merchant originator limited to `PAY_SUPPLIER` and `BRANCH_FUND_TRANSFER` financial request types.

The current implementation treats a provider outcome that may have produced an external financial effect as `RECONCILIATION_REQUIRED` and blocks retries under that UTT. The October extension proposes independent RTT fencing and split-lineage replay; a universal outbound wrapper; and more extensible partner adapters. RailOne also intends to allow institutions to build conformance-tested adapters under a bounded trial and paid license model.

**Decision objective:** increase parallelism across unrelated transactions and reduce adapter coupling without allowing duplicate economic effects, untrusted adapter authority, non-deterministic route mutation or unlicensed new production dispatch.

## 2. Architectural decision

**Adopt four linked, independently enforced controls:**

1. **RTT operational fence:** isolate the state machine and reconciliation work of a specific attempt without blocking unrelated UTTs or global workers.
2. **UTT economic-effect fence:** independently prevent a financially equivalent *new dispatch* under the same commercial intent when any previous provider attempt might still execute or settle. A signed cancellation request, transport timeout or SLA indemnity does **not** release this fence; only qualifying provider/no-effect evidence and RailOne-controlled reconciliation may do so.
3. **Canonical RailOne Standard Wrapper (CRSW):** an internally signed, versioned, minimal-permission dispatch envelope projected through an untrusted institution adapter into an institution-specific request. Adapters cannot modify canonical intent, authorize additional attempts, claim finality or issue licenses.
4. **InstitutionLicenseGrant (ILG):** an independently governed commercial permission bound to institution, adapter versions, permitted scope and time. It is **not** an ETK, transaction authorization, regulatory authorization or proof of settlement. Its status and quota are enforced by RailOne's trusted control plane.

**Non-negotiable rule:** an unknown effect on RTT-1 may be reconciled asynchronously, but a second economically equivalent route must not dispatch merely because RTT-1 is operationally fenced. If the current UTT describes one indivisible payment, this restriction remains UTT-scoped; granularism improves isolation and network throughput for *other UTTs*, not duplicate-risk permission for the same one.

## 3. Retained invariants

- Exactly one accepted commercial intent yields one immutable, signed UTT and at most one customer charge. RTT attempts do not own customer pricing.
- UTT must precede one persisted ExecutionPlan; RTT signed birth artifacts are immutable and link to that UTT, plan, route, adapter, prior RTT and policy evidence.
- Sender/receiver attestations (`ETK-S`, `ETK-R`) remain purpose-bound. ETKs are not signing keys, license grants or settlement proofs.
- Route decisions consume recorded, fixed-point inputs with explicit deterministic tie-breaking; all mutations are append-only and attributable.
- An external `ACCEPTED_FOR_PROCESSING` is not settlement. Finality requires external evidence plus the prescribed reconciliation checks.
- No RailOne custody, spendable balance or provider account authority is created by this ADR.
- Unknown external effect cannot be deemed safe to replay solely from a local timeout, cancellation digest, adapter self-report, unverified callback or SLA.
- License or adapter expiry must not interrupt reconciliation, safe incident handling or evidence collection for existing attempts.

## 4. Operational and economic-effect fencing

### 4.1 Independent dimensions

An RTT may transition to `RECONCILIATION_REQUIRED`, while its operational worker releases its own lease. The related **economic-effect fence** remains `BLOCKED_UNKNOWN` until evidence establishes `NO_EFFECT_CONFIRMED`, or reaches `EFFECT_CONFIRMED`/`SETTLED` and closes execution. A `CANCEL_REQUESTED` event means only a cancellation instruction was issued. `CANCEL_CONFIRMED_NO_EFFECT` requires provider-specific, independently verifiable confirmation that the original payment cannot later take effect. Where a provider cannot establish that property, hold and reconcile rather than reroute.

Avoid interpreting the proposed `SPLIT_NON_BLOCKING` flag as authority to emit another financial effect. For compatibility it may describe asynchronous **operational processing only**; the authoritative dispatch guard is the separate economic-effect fence. Do not introduce simultaneous economically active RTTs under a single indivisible UTT.

### 4.2 Dispatch permit

Before enqueueing or dispatching a provider instruction, the core MUST atomically verify: signed UTT and ETK scope; current ExecutionPlan version and route eligibility; exact adapter binding/conformance; effect-fence release; attempt/budget limits; valid ILG entitlement and quota reservation; and a stable idempotency reference. A short-lived, scope-bound, signed `DispatchPermit` is then associated with the RTT/outbox record. Dispatch workers recheck revocation/fence state at the authoritative boundary. The adapter cannot mint permits.

### 4.3 Cancellation semantics

The proposed deterministic SHA-256 cancellation binding can be retained as a *request identifier*, but any signed cancellation instruction must also bind the exact original RTT, adapter/provider, external reference where known, action, expiry, nonce/replay protection and key domain. Signature proves instruction authenticity, **not external cancellation success**. A provider-corroborated final cancellation or no-effect outcome is a separate evidentiary artifact.

### 4.4 Atomic persistence

Implement fencing in the existing PostgreSQL `railone` schema, not as an unconnected parallel ledger. Use a per-UTT/per-economic-effect uniqueness guard, compare-and-swap plan version, persisted lease/fence epochs and one transaction for mutation + dispatch reservation + outbox event. Index open attempts by UTT/status/epoch and relevant adapter correlation fields. Do not claim microsecond performance from index design alone; benchmark representative production-shaped workloads. Redis is a cache/coordination aid, not the final authority.

## 5. Canonical RailOne Standard Wrapper

### 5.1 Ownership and permitted transformations

CRSW is **RailOne-core-generated**, schema-versioned and signed. It is the only core-to-adapter instruction format. The adapter projects a minimum-necessary provider payload from the signed canonical envelope, resolved account bindings and a declarative provider mapping profile. It may normalize syntax and transport but MUST NOT alter UTT commercial terms, RTT lineage, trust assertions, designated beneficiary, permit scope or license decision. The core independently verifies inbound normalized events and external settlement evidence.

Raw sender MSISDN and beneficiary account numbers MUST NOT appear in the common wrapper, logs, manifests, conformance traces or partner repository. Instead carry opaque, short-lived `payer_binding_ref` and `beneficiary_binding_ref`. Sensitive endpoints are fetched only at authorized dispatch from a protected account-binding service, and only the minimum fields are revealed to the specific adapter/transport. Sender and receiver ContUIDs should likewise be omitted from provider-specific projections unless required and authorized.

### 5.2 Illustrative canonical wrapper — synthetic Uganda MTN → Tanzania CRDB scenario

This is a **draft test vector**, not a signed or routable production message. All digests, signatures, IDs, provider capabilities and timestamps require real generation/verification. The original example's amount interpretation is ambiguous; this draft assumes `100,000 UGX` and `71,500 TZS` as displayed currency values, with `receive_amount_minor = 7,150,000` **only if** the agreed TZS scale is two decimals. Final amounts MUST be copied from the accepted UTT and authoritative currency-exponent policy, never recomputed by the adapter.

```json
{
  "railone_standard_wrapper": {
    "schema_version": "1.1.0-draft",
    "message_type": "INSTITUTION_EXECUTION_DISPATCH",
    "envelope_id": "env_synthetic_0003",
    "issued_at": "2026-11-04T12:00:00Z",
    "expires_at": "2026-11-04T12:00:30Z",
    "trace_identifiers": {
      "utt_id": "utt_01HK7PQ81B2KC4RE7V0X9Z4A2A",
      "plan_id": "plan_01HK7PR54V1ND3CQ9W0X8B5F2M",
      "rtt_id": "rtt_01HK7RZ99M4NF5ST8W1X9Z5D8M",
      "correlation_id": "corr_p2p_991823a",
      "attempt_number": 3,
      "replay_generation": 2
    },
    "bilateral_trust_anchors": {
      "utt_payload_digest": "<verified-sha256-hex>",
      "rtt_birth_digest": "<verified-sha256-hex>",
      "etk_s_digest": "<verified-sha256-hex>",
      "etk_r_digest": "<verified-sha256-hex>",
      "sender_cont_uid": "CUID-UG-7721A",
      "recipient_cont_uid": "CUID-TZ-8834B"
    },
    "commercial_terms": {
      "source_amount_minor": 100000,
      "source_currency": "UGX",
      "receive_amount_minor": 7150000,
      "receive_currency": "TZS",
      "pricing_model": "PER_INTENT"
    },
    "execution_binding": {
      "route_id": "route_tips_direct_clearing",
      "adapter_binding_ref": "tips_settlement_spi@0.15.0",
      "adapter_manifest_digest": "<verified-sha256-hex>",
      "route_decision_digest": "<verified-sha256-hex>",
      "idempotency_key": "idmp_synthetic_gen2",
      "dispatch_permit_id": "permit_synthetic_003"
    },
    "fencing_controls": {
      "operational_mode": "ASYNC_RTT_RECONCILIATION_SUPPORTED",
      "economic_effect_fence_epoch": 4,
      "dispatch_guard_decision": "RELEASED_FOR_THIS_ATTEMPT",
      "cancellation_evidence_ref": "recon_no_effect_synthetic_002"
    },
    "protected_account_bindings": {
      "payer_binding_ref": "acctbind_opaque_ug_01",
      "beneficiary_binding_ref": "acctbind_opaque_tz_01",
      "source_routing_node": "UG-MTN-MOBILE-MONEY",
      "destination_routing_node": "TZ-CRDB-BANK-PLC"
    },
    "institution_entitlement": {
      "institution_id": "institution_synthetic_01",
      "license_grant_id": "ilg_synthetic_01",
      "license_decision_ref": "ild_synthetic_003"
    }
  },
  "signature_envelope": {
    "artifact_domain": "railone.dispatch-envelope.v1",
    "algorithm": "Ed25519",
    "signer_key_id": "<railone-core-signing-key-id>",
    "payload_sha256": "<digest-of-canonical-wrapper>",
    "signature": "<base64url-signature>"
  }
}
```

**Important:** `fencing_controls`, license references and signature fields here are **core-generated assertions**, not client-supplied evidence that should be blindly trusted. The signed wrapper plus a current server-side check authorizes only one intended dispatch; it does not give an adapter indefinite privilege. The `route_tips_direct_clearing` name is retained from the supplied synthetic scenario and does not establish a real cross-border TIPS route.

### 5.3 Adapter projection and normalized response

For an approved adapter, the egress projection may contain exactly the mapped provider instruction, recipient and payer endpoints resolved just-in-time, provider idempotency reference, transport auth context and correlation references. No pricing policy, license secrets, unrelated identities, upstream private keys or route-scoring authority is exported.

Inbound adapter events use a separate versioned `InstitutionOutcomeEnvelope` with pinned adapter identity, external reference, outcome (`ACCEPTED_FOR_PROCESSING`, `OUTCOME_UNKNOWN`, `CONFIRMED_FAILURE`, `CONFIRMED_SUCCESS`, etc.), finality level, normalized amount, evidence digest and verification provenance. Core normalization does not turn a self-reported `CONFIRMED_SUCCESS` into final settlement without corroborating evidence.

## 6. InstitutionLicenseGrant and partner SDK

### 6.1 Separate primitives

Introduce an immutable, signed `InstitutionLicenseGrant` including `grant_id`, `institution_id`, authorized adapter/version and manifest digest(s), environments, corridors, rails, currencies, allowed operations, `valid_from`, `expires_at`, trial/commercial tier, applicable quota policy/version and signer. Changing rights issues a new grant. Maintain append-only `InstitutionLicenseEvent` revocation/suspension history and signed `InstitutionLicenseDecision` records for each dispatch-admission check. Cache is advisory; trusted RailOne services decide.

**No `etk_l` or `ETK-L`:** licensing is institutional commercial entitlement. ETK-S/ETK-R remain participant execution trust assertions. A grant is also not an institution's proof of regulator approval, scheme membership, settlement capability or conformance by itself.

### 6.2 Trial interpretation (OPEN commercial decision)

Working assumption: **USD 25,000 per calendar month is the trial's aggregate processed-value cap**, not a USD 25,000 license fee. If the figure is instead a subscription price, remove the volume cap and define pricing in the commercial contract. If a cap applies: use immutable FX valuation/quote policy; a UTC monthly window (subject to commercial agreement); ledger entries keyed by institution + UTT + period; atomic quota reservations, adjustments and no double-counting of RTT replay. Never count every retry as a new commercial transaction. On expiry or cap exhaustion, block **new** unauthorized dispatch and/or acceptance according to the admission policy, while preserving existing settlement, callback and reconciliation duties. Live trials still need all applicable legal and partner approvals.

### 6.3 External adapter repository

Publish a deliberately bounded SDK/repository containing `schemas/` (wrapper and event contracts), `adapter_sdk/` (SPI and typed models), `examples/` (synthetic adapter), `conformance/` (local tests and test vectors), and `docs/` (onboarding, security and operational requirements). Do **not** publish RailOne routing authority, internal private keys, production credentials, licensed-entitlement decision engine, actual account bindings, privileged core migrations or unreleased security policy. Partner code runs in a segregated runtime with least privilege, tenant-scoped credentials, outbound allowlists, bounded resources and observable signed events.

## 7. Worked synthetic scenario and safety gates

| Sequence | Event | Operational result | Economic-effect result |
|---|---|---|---|
| 1 | UTT accepted for Uganda MTN → Tanzania CRDB | Plan created; RTT-1 to synthetic Hub A submitted | One intended payment reserved |
| 2 | Hub A times out **after possible submission** | RTT-1 becomes `RECONCILIATION_REQUIRED`; worker is isolated | **BLOCKED_UNKNOWN**: no RTT-2 dispatch |
| 3 | RailOne sends signed cancellation/status request | Background reconciliation proceeds; unrelated UTTs remain active | Still blocked; request is not proof |
| 4 | Provider evidence establishes final **no effect** for RTT-1 | Signed no-effect reconciliation event recorded | Fence released for next authorized attempt |
| 5 | RTT-2 to synthetic Hub B is rejected with verifiable no effect | Record confirmed failure; re-score using recorded telemetry/policy | Safe to permit another attempt if limits allow |
| 6 | RTT-3 through approved synthetic alternate settles | Reconcile provider evidence; mark UTT final once | Close further dispatch, retain evidence |

If step 4 cannot establish irreversible no effect, RailOne must remain blocked for that UTT's equivalent payment despite processing other UTTs normally. If a provider later contradicts its no-effect statement, trigger an incident and dispute/recovery process; no protocol can eliminate fraudulent or inconsistent downstream settlement behavior by signature alone.

## 8. Deterministic decision records and safety tests

Persist a signed or content-addressed `RouteDecisionRecord` containing the UTT/plan digest, routing-policy version, deterministic scorer weights, exact candidate and telemetry snapshots, hard-filter reasons, stable tie-break order, route penalties, chosen route, adapter version, budget, decision sequence/epoch and previous record digest. Use integer minor units and fixed-point calculations; prohibit floating point in consensus-relevant decisions. Persist decision + fence + outbox mutations atomically. Re-run test vectors across releases and implementations to prove reproducibility.

The conformance suite MUST verify at least: malicious wrapper-field changes, raw-account data leakage, stale permit replay, wrong adapter/version, out-of-scope licensing, license expiry or quota race, duplicate quote and submission, timeout-after-submit, forged cancellation, late callback, missing no-effect proof, mismatched settlement amount, state CAS races, deterministic route reproduction, adapter crash/restart, and reconciliation after license revocation.

## 9. Rollout and acceptance gates

1. Approve revised RTT/economic-fence invariants and update controlled specs; retain old unknown-outcome replay safety until replaced by proven stronger behavior.
2. Add immutable route decisions, effect-fence records, dispatch permits and atomic migrations in the existing `railone` schema, with concurrency tests before enabling split processing.
3. Introduce wrapper schemas, signing, canonicalization, SDK projection sandbox and normalized result verification. Do not place plaintext account endpoints in the common wrapper.
4. Add ILG grant, authorization events and quota ledger; enforce at RailOne authorization/dispatch boundaries, never only in external adapter code.
5. Extend partner conformance and run adversarial tests plus partner-sandbox shadow trials. Promote no live funds based only on synthetic success.

**Go/no-go criterion:** no replay under ambiguous economic effect; one charge per UTT; no unauthorized adapter execution or license bypass; deterministic decisions reproducible; no plaintext endpoint leakage through canonical or audit surfaces; and conformance evidence independently captured by RailOne.

## 10. Open decisions

- Is USD 25,000/month a trial processed-value ceiling, a license fee, or both? Define USD valuation, rounding, monthly cutoff, reversals and accounting events.
- Which institutions provide strong, enforceable no-effect/cancellation evidence for safe route replays? Which are permanently hold-and-reconcile-only?
- Which RailOne core signer and isolated deployment component owns the `DispatchPermit`? What are revocation/cache TTL and fail-closed rules?
- What exact adapter execution runtime and sandbox isolation architecture will be supported for externally supplied code?
- Which sender/receiver identity fields may legitimately cross particular partner/corridor boundaries? Define per-profile data minimization.
- Define formal currency exponent and normalization for the synthetic UGX/TZS test vector before approving it as a canonical conformance fixture.

## 11. Implementation impact map

- `railone_execution/{models,service,store,scoring}.py`: economic fence, RTT lifecycle, deterministic route decisions and dispatch permit checks.
- `railone_operations/{models,service}.py`: atomic outbox admission, idempotency, external effect/cancellation evidence.
- `railone_institutions/{models,spi,registry,manifest}.py`: canonical wrapper contract, adapter projection and exact version/permission checks.
- `railone_crypto/{canonical_json,signature_service}.py`: versioned dispatch-envelope domains and signed decision/permit artifacts.
- `railone_certification/`: adversarial and licensing conformance cases.
- New `railone_licensing/` and matching `railone_postgres/` repositories/migrations: grants, entitlement decisions, usage ledger and revocation.
- New partner-only adapter SDK distribution: contract-tested extract of public interfaces, not the entire RailOne Core.

**Disposition:** PROPOSED pending protocol, security, engineering, commercial and applicable partner/regulatory review.
