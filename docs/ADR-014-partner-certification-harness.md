# ADR-014: Partner Sandbox Certification Harness

- Status: Accepted
- Date: 2026-07-14
- Scope: RailOne Step 11E partner integration pilot

## Context

An adapter interface and signed capability manifest do not prove that an
institution integration preserves RailOne semantics under retries, timeouts,
duplicate callbacks, evidence mismatch or authorization boundaries. Partner
teams also need a repeatable sandbox gate that produces comparable audit
evidence without exposing account references, access tokens or customer data.

## Decision

RailOne adopts a capability-aware partner certification suite. A trusted driver
executes prescribed scenarios against the sandbox system under test and returns
a content-addressed canonical trace. RailOne independently evaluates the trace
for event counts, order, identifiers and forbidden state transitions.

The comprehensive suite covers:

1. P2P settlement and sender/receiver history;
2. Avia merchant/supplier settlement through merchant and branch scopes;
3. cross-border FX-bound settlement where the manifest supports it;
4. idempotent duplicate submission;
5. unknown outcome followed by reconciliation;
6. tampered callback rejection;
7. duplicate callback exactly-once finality;
8. settlement amount mismatch rejection;
9. transaction-history access control;
10. SMS creation only after verified finality; and
11. exact adapter-version pinning.

The authoritative coordinator verifies the Ed25519-signed capability manifest,
checks its validity and certification state, binds the same exact adapter
version, derives the suite from declared capabilities, executes the cases and
signs the final report. Failed reports are also signed so failure evidence
cannot be erased or rewritten.

## Trust boundary

The included synthetic reference driver proves the harness itself only. It is
classified `SYNTHETIC_SELF_TEST` and the signing service refuses it. A partner
report requires `PARTNER_SANDBOX` evidence from a driver controlled by the
RailOne integration environment. The offline CLI deliberately emits unsigned
draft reports.

## Consequences

- Integration behavior becomes repeatable and comparable across institutions.
- A green report is necessary but insufficient for production.
- Partner sandbox traces must be collected from RailOne audit boundaries, not
  hand-authored by the partner.
- Production promotion additionally requires bilateral certification,
  security review, reconciliation, resilience, legal and regulatory gates.
