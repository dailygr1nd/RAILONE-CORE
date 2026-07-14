# Step 11D institution adapter onboarding runbook

## Purpose

Use this runbook to add a bank, mobile-money operator, domestic switch or
cross-border provider without importing partner semantics into RailOne core.
This release authorizes synthetic integration only.

## Onboarding sequence

1. Assign stable institution, provider, network and adapter identifiers.
2. Record supported source/destination institutions, countries, currencies,
   rails, amount limits and finality evidence mechanisms.
3. Choose the message profile and document every field mapping. Validate ISO
   20022 messages against the exact scheme XSD and usage rules when applicable.
4. Configure HTTPS transport, trust anchors, mTLS client identity and OAuth
   token flow. Never place private keys or client secrets in the repository.
5. Implement explicit mappings for accepted, retryable rejected, terminal
   rejected, pending, settled, failed and unknown provider codes.
6. Implement and authenticate callbacks, active status queries and/or
   reconciliation. At least one evidence path is required to claim settlement.
7. Run the shared conformance suite plus partner contract tests, malformed input,
   timeout, replay, duplicate callback and reconciliation-conflict scenarios.
8. Sign the capability manifest with the isolated Ed25519 execution signer and
   persist it append-only.
9. Promote from `DRAFT` to `CONFORMANCE`, then to `CERTIFIED` only after the
   bilateral technical, operational, security and legal gates pass.
10. Canary synthetic traffic, verify metrics and reconciliation, then approve a
    separately controlled production cutover.

## Required invariants

- The user-selected debit and receiver credit account bindings remain opaque.
- Raw endpoints are resolved only at dispatch and must not enter logs or signed
  capability manifests.
- The RTT adapter binding is exact and immutable.
- A timeout after sending is unknown, never assumed failed.
- Provider acceptance is processing, never settlement.
- Unknown outcomes block reroute until status or reconciliation resolves them.
- One UTT is charged once; RTT retries do not create another customer charge.
- Adapters cannot mutate identity, UTT, execution-plan or history state.

## Pilot profiles

- Domestic bank: synthetic KES account transfer/RTGS behavior.
- Domestic instant switch: synthetic PesaLink-like capability shape, with no
  claim of PesaLink affiliation or certification.
- Cross-border: synthetic multi-currency aggregator shape, with no claim of
  Thunes affiliation or certification.
- M-PESA: retain the existing provider-specific B2C adapter and callback
  processor while migrating it behind `InstitutionAdapterBridge` in a partner
  contract-test environment.

## Go-live evidence

Retain the signed manifest, conformance report, message/XSD results, certificate
inventory, OAuth scopes, callback verification proof, reconciliation results,
load tests, failure drills, support contacts, SLA, data-processing terms and
regulatory approvals. A green generic conformance suite alone is insufficient.
