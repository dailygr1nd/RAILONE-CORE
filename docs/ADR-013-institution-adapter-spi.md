# ADR-013: Institution Adapter SPI and Capability Trust

- Status: Accepted
- Date: 2026-07-14
- Scope: RailOne Step 11D simulated integration pilot

## Context

The existing provider contract could submit a request but could not express an
institution's corridors, rails, currencies, limits, authentication, status,
callback, reconciliation or evidence-finality behavior. A single universal
adapter would hide material differences between a bank, mobile-money operator,
domestic switch and cross-border aggregator.

## Decision

RailOne adopts one canonical institution SPI with provider-specific plug-ins.
Each plug-in publishes an expiring Ed25519-signed capability manifest. Route
discovery may consider matching active manifests, but every signed RTT carries
one exact `adapter_id@adapter_version` binding. Dispatch fails if the loaded
adapter differs from that binding.

The SPI separates:

1. capability and certification metadata;
2. authentication and TLS transport;
3. JSON, ISO 20022 or proprietary message codecs;
4. submission outcome normalization;
5. callback authentication and normalization;
6. active status and reconciliation evidence; and
7. adapter health.

Submission acceptance has at most `PROCESSING` finality. Only authenticated,
correlated external evidence may assert credit confirmation or settlement.
Transport failure after dispatch becomes `OUTCOME_UNKNOWN`, which preserves the
existing no-blind-retry invariant.

## Ownership boundary

Adapters translate and normalize external systems. They do not create or mutate
UTTs, choose a new route, issue RTTs, decide customer charges, project ContUID
history, or declare settlement without partner evidence. Those remain RailOne
core responsibilities.

## Security profiles

For synthetic pilot traffic, TLS 1.2+ (TLS 1.3 preferred), isolated secrets,
short-lived tokens where supported, authenticated callbacks, Ed25519 artifact
signatures and AES-256-GCM envelopes are required. Simulation no-auth is allowed
only for local/synthetic endpoints.

For production, each partner profile must select mTLS and OAuth 2.0 sender-
constrained access tokens; FAPI 2.0 and DPoP may be selected where ecosystem
support requires them. Certificate rotation, trust-anchor governance, replay
controls and independent scheme certification are operational requirements, not
properties inferred from the generic SPI.

## Consequences

- RailOne gains a stable integration surface without pretending all institutions
  behave alike.
- Adapter upgrades are new immutable versions, not in-place replacement.
- A manifest makes routing eligibility auditable but does not prove a partner
  commercial agreement or scheme certification.
- ISO 20022 support remains profile- and scheme-specific; generic XML generation
  alone is not interoperability certification.
