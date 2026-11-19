# ADR-026 — R1-IOS-001 Institutional Legal Identity Admission (first slice)

**Status:** Implemented as a bounded institutional-identity foundation; *not* live network admission.
**Baseline:** RailOne v0.18 snapshot, migrations 0001–0020. New append-only migration: `0021_institutional_identity_admission.sql`.

## Decision

An institution is a verified **legal entity**, not a human RIO/CUID. Allocate a
stable, opaque `INST-{ISO2}-{CLASS}-{16_BASE32_CHARS}` ID with cryptographically
random 80-bit suffix. ISO2 denotes **original incorporation/home jurisdiction**,
not permanent transaction eligibility. CLASS is `BNK`, `MNO`, `PSP`, `AGG`, `SWI`,
or `EMI`; it classifies onboarding and does not assert a regulatory license.
Different legal entities require separate identifiers; multiple adapters may
belong to one institution. The identifier is immutable after creation.

Separate three authority domains:

1. **Institution legal identity** (`railone.institution_identity_registry`) —
   legal identity claims and institutionally referenced compliance evidence.
2. **Institution authorization** (existing `railone.partner_institutions` and
   future capability approval policy) — whether a particular institution may
   participate, in what roles and territories. **This slice does NOT activate it.**
3. **Institution adapter capability** (existing signed, expiring, version-pinned
   `InstitutionCapabilityManifest` and certification) — what a particular
   adapter claims and has been tested to perform.

The institute submits legal name, display name, home jurisdiction, type,
registration reference and **opaque** regulatory evidence references. Those
claims remain `PENDING_VERIFICATION`. The registry rejects duplicate
`(home_jurisdiction, registration_reference)` combinations.

Only an authorized RailOne compliance signer (default `iss=RAILONE`) holding a
dedicated `INSTITUTION_ONBOARDING_SIGNING` Ed25519 key may attest verification.
The signed `railone.institution_onboarding_attestation` envelope must commit to:

```json
{
  "version": 1,
  "institution_id": "INST-KE-PSP-AAAAAAAAAAAAAAAA",
  "application_sha256": "<SHA256-of-canonical-application>",
  "decision": "LEGAL_AND_REGULATORY_VERIFIED",
  "evidence_ref": "DUE-DILIGENCE-CASE-001",
  "evidence_sha256": "<SHA256-of-verified-evidence>",
  "expires_at": 1797770000
}
```

The verifier independently checks the underlying documents and licensing
status **before** signing. The service verifies key purpose, trusted issuer,
identity binding, exact claims, signature, timestamps, evidence reference and
expiry. `require_verified` rechecks the signature, expiry and key revocation.
A signed self-declaration by the applying institution is never sufficient.
The signed decision is retained with a separate append-only event table. Private
licence documents, beneficial ownership and contact PII must remain in a
restricted, encrypted evidence store; only opaque references and digests belong
in the registry. The registry must not be exposed as a public API.

See `docs/fixtures/institution-application-synthetic-v1.json` for an unsigned
synthetic application matching `InstitutionApplication.to_payload()`. This is
not an HTTP endpoint and must not be interpreted as an approved institution.

## Explicitly out of scope

- No routes or public onboarding APIs yet; registration is an internal service.
- No `PartnerInstitution.ACTIVE` flip, adapter activation, account verification,
  customer discovery, settlement, routing or transaction permissions.
- No automated legal verification; signed approval must originate from an
  independent, authorized review process/HSM/KMS, not applicant credentials.
- No entity-group hierarchies, license renewal/appeals, ownership changes,
  verification amendment, suspension/offboarding, multi-person approvals or
  dedicated institutional revocation lifecycle yet. Expired/revoked evidence
  **fails closed** until those processes are designed.
- No changes to human RIG/RIO/RIV, CUID, customer onboarding, delegated ETK-R,
  sender-first ETK-S→ETK-R→UTT→ExecutionPlan→RTT, or noncustodial settlement.

## Engineering usage (sandbox only)

```python
from datetime import datetime, timedelta, timezone
from railone_institutions import InstitutionApplication, InstitutionClass, InstitutionOnboardingService
from railone_postgres import PostgresInstitutionIdentityRepository, PostgresDatabase

service = InstitutionOnboardingService(
    repository=PostgresInstitutionIdentityRepository(database),
    signatures=trusted_signatures,
)
record = service.register(InstitutionApplication(
    legal_name="SavannaPay Processing Ltd", display_name="SavannaPay",
    institution_class=InstitutionClass.PSP, home_jurisdiction="KE",
    registration_reference="SYN-KE-REG-001",
    regulatory_evidence_refs=("EVID-REG-001", "EVID-LICENSE-001"),
))
# A separate compliance verifier signs the exact record.application.fingerprint
# and record.institution_id using a dedicated onboarding-signing key.
# verified = service.verify(record.institution_id, signed_compliance_decision)
# STILL NOT AUTHORIZED FOR PAYMENT EXECUTION.
```

## Checks and upgrade

Run `python -m unittest -v tests.test_institution_identity_onboarding` then
`python run_tests.py`. The migration runner adds migration 0021 non-destructively.
Use the established disposable PostgreSQL suite for a live migration gate;
**do not** reset any shared or production schema with demo scripts.
Keep 0021 unchanged after it has been applied (checksum locked).

Follow-up: certification-backed `institution_identity -> approved permissions ->
signed capability manifest -> client discovery` gates, PostgreSQL/HTTP integration,
regulatory jurisdiction policy, signed verification renewal and revocation,
append-only approval events, and institutional account-binding validation.
