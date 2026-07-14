# ADR-002: Identity Continuity and Execution Authority

- Status: Accepted
- Date: 2026-07-14
- Depends on: ADR-001

## Identity decision

RailOne identity continuity is represented by three separate objects:

- RIG records immutable genesis evidence.
- RIO is the stable public continuity object.
- RIV records mutable trust revisions.

The public RailOne identity and continuity UID do not contain trust tier or
revision. Trust changes create RIVs rather than replacing identity.

For pilot continuity, RailOne derives a versioned keyed fingerprint from an
institutionally verified provider subject reference. The derived continuity UID
contains 160 bits encoded with Base32. The HMAC key must live outside the source
repository and application database.

The provider subject reference is transient input. It is not persisted inside
RIG, RIO, RIV, or the public identity projection. Cross-provider identity
linking is a governed operation and must not be inferred automatically.

An identity cannot enter a verified trust tier without a valid Ed25519
institutional attestation containing a provider, verification reference,
evidence hash, trust tier, issuance time, and expiry.

## ETK decision

The external protocol names ETK-S and ETK-R are retained for continuity, but
they are authorization attestations rather than encryption or signing keys.
Private Ed25519 signing keys are separate infrastructure secrets.

ETK-S proves that an authenticated sender or authorized merchant actor approved
execution of a specific persisted UTT under a specific accepted quote. It is
bound to amount, currency, origin context, authorization reference, issue time,
expiry, and the non-custodial execution scope.

ETK-R proves receiver participation or beneficiary eligibility. Supported modes
are:

- `ACTIVE_ACCEPTANCE`
- `BENEFICIARY_PREAUTHORIZED`
- `DIRECTORY_RESOLUTION`
- `INTERNAL_MERCHANT_AUTHORITY`
- `PASSIVE_CREDIT`

Only `ACTIVE_ACCEPTANCE` may assert `receiver_confirmed=true`. Every ETK-R must
reference and cryptographically validate its ETK-S, belong to the same UTT, and
expire no later than the ETK-S.

## Consequences

- The legacy random eight-hex continuity UID is superseded.
- Plain SHA-256 reconstruction is not valid attestation verification.
- RailOne cannot create ETK-R and call it receiver confirmation without evidence.
- ETK identifiers are opaque content identifiers; their authority comes from
  the signed envelope, key purpose, and verified evidence.
- Durable persistence and database constraints will be added with the canonical
  execution schema after the domain contracts stabilize.
