# ADR-018: Signed Canonical Institution Dispatch Wrapper (Phase 3)

- **Status:** Proposed — review candidate, no live-funds approval
- **Scope:** Canonical cross-boundary instruction artifact; NOT a dispatch permit
- **Baseline:** v0.16 Alpha Phase 2 (ADR-017 and migrations 0001–0012)
- **Migration:** `0013_signed_institution_dispatch_wrappers.sql`
- **Related:** ADR-013 (Institution SPI), ADR-014 (partner conformance), ADR-017 (route decision), RO-DOC-TERM-001, RO-DOC-RTT-006

## Context

Institutions will develop independent RailOne adapters. Adapters must receive a
standard, strictly bounded description of an already-authorized intent rather
than mutable access to RailOne core objects. The v0.15 SPI already maps provider
messages, but its current compatibility bridge can submit `ProviderExecutionRequest`
without requiring the new signed wrapper. This ADR **does not yet close that
legacy dispatch path**. The next integration gate must do so before live funds.

## Decision

Define `CanonicalDispatchWrapper` with exact schema version `1.0.0` and message
kind `INSTITUTION_EXECUTION_DISPATCH`. Its contents are:

1. **Trace identifiers:** UTT, ExecutionPlan, RTT, correlation, attempt number,
   replay generation.
2. **Bilateral trust anchors:** SHA-256 digests of verified UTT, RTT, ETK-S and
   ETK-R artifacts and sender/receiver continuity identifiers.
3. **Commercial terms:** positive integer minor-unit amounts, three-letter
   currency codes, `PER_INTENT` and `NON_CUSTODIAL`.
4. **Execution binding:** route, exact adapter semantic version, manifest digest,
   immutable initial route decision digest, provider, idempotency key and request digest.
5. **Fencing references:** sequential mode, fence epoch, asserted dispatch guard
   decision and optional reconciliation release evidence reference. A replay RTT
   must carry a release reference.
6. **Protected endpoint bindings:** opaque binding references only, never an
   MSISDN, account number, beneficiary name, access token, credential or secret.

For now, `SPLIT_NON_BLOCKING` is rejected at the wrapper schema boundary.
Parallel economic-effect dispatch requires a separate reviewed granular fencing
implementation, not a message flag.

Each wrapper has a domain-separated content-addressed ID, short expiry (maximum
60 seconds), and an Ed25519 `INSTITUTION_DISPATCH_WRAPPER` signature produced by
RailOne's existing `SignatureService` with an execution-signing key.
`DispatchWrapperService.verify()` checks signature type, trusted signer owner,
issuer time, envelope validity, exact content equality and a separately loaded
`AuthoritativeDispatchSnapshot`.

The snapshot must be assembled by a *trusted RailOne core component* from
persisted, authenticated UTT/RTT/ExecutionPlan, ETK, decision, manifest, account
binding and economic-fence state. An externally supplied snapshot or an embedded
`dispatch_guard_decision` value is not authoritative. If a snapshot can be
constructed solely from untrusted wrapper contents, binding verification is
meaningless.

## Persistence

Migration 0013 introduces append-only `institution_dispatch_wrappers` storage
with foreign keys to RTT, UTT, plan, initial route decision and exact institution
adapter manifest. The table stores the complete signed envelope, signer key ID,
content digest and 60-second validity window. One RTT has at most one persisted
wrapper; conflicting copies fail closed. Raw endpoints must not be inserted into
this table. The database rejects mutation, but downstream systems still need
cryptographic verification of stored artifacts.

## Security and non-claims

- **A wrapper is NOT a payment authorization.** Signature verification alone
  does not prove funds can be dispatched.
- The existing provider submission coordinator and unknown-outcome safety model
  remain unchanged. The wrapper is an **additive, not yet mandatory**, protocol
  capability. It must not be represented as integrated end-to-end.
- An adapter must never choose its own route, change accepted UTT amounts,
  mutate an RTT or assert settlement without correlated provider evidence.
- Neither a hash nor a wrapper guarantees provider cancellation, settlement,
  regulatory authorization, malicious-adapter isolation or license validity.
- `InstitutionLicenseGrant` is **not** included; entitlement checks belong to a
  separately reviewed trusted admission decision.
- The reference is a Python class contract. An external SDK should ship a
  language-neutral canonical JSON/JSON Schema plus conformance vectors and
  signature-validation rules before partner distribution.
- Current wrapper construction permits a caller to supply the snapshot. That is
  suitable for controlled tests, **not sufficient for live funds**. A trusted
  snapshot resolver and mandatory admission gateway must be added next.

## Acceptance tests

- Same semantic payload reorders identically, with an immutable digest.
- Unknown fields, extra nesting, raw account identifiers, non-minor-unit
  floats, bad currency codes, unsupported custody and unrecognized operational
  modes are rejected.
- Tampered Ed25519 signatures, different artifact type, untrusted signer,
  expired wrapper and differing authoritative route, amount, provider, ETK,
  binding, decision or fence reject before outbound operation.
- In-memory and PostgreSQL stores never rewrite an RTT's signed wrapper.
- Older UTT/RTT tests remain green; no current dispatch flow is altered.
- Migration 0013 executes and rolls back correctly on **disposable PostgreSQL**;
  audit append-only triggers and FK constraints with real queries.

## Next integration gates (not part of Phase 3)

1. Implement trusted admission-snapshot resolver using canonical persisted
   records and independently verified signatures/evidence, not user input.
2. Require signed-wrapper and admission verification at every institution
   dispatch path, including the legacy provider bridge and all retries.
3. Add signed short-lived dispatch permits with atomic economic-effect fencing;
   a valid wrapper must never bypass uncertainty, idempotency or replay gates.
4. Add mutually authenticated isolated institution-adapter runtimes, strict
   command and response schemas, capability/quota/entitlement checks and
   attested partner conformance.
5. Test against real disposable PostgreSQL and controlled provider sandboxes;
   never treat this unit-test suite as permission for live money movement.
