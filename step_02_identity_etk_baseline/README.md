# RailOne Pilot Convergence - Step 02

This cumulative batch contains the Step 01 cryptographic baseline and adds the
identity-continuity and execution-authority foundations required before UTT
creation.

## What this step locks

- Ed25519 is the canonical signature algorithm for RailOne-owned artifacts.
- Ed25519 signs data; it does not encrypt data.
- Private keys are never stored in the repository or returned by the key
  registry.
- Every signature carries an algorithm, curve, key identifier, artifact type,
  version, issuer, issue time, and payload hash.
- Quote, execution, identity, settlement, and replay signing are separate key
  purposes.
- JSON payloads are serialized deterministically and floating-point numbers are
  rejected from signed financial artifacts.
- Key rotation and revocation are part of verification semantics.
- A RailOne continuity identifier is derived from a versioned keyed digest and
  contains 160 bits of collision-resistant output.
- Raw national identifiers and raw provider subject identifiers are not stored
  in identity continuity objects.
- RIG is immutable genesis evidence, RIO is the stable public continuity object,
  and RIV contains mutable trust evolution.
- Institutional identity claims require a valid Ed25519 attestation.
- ETK-S is a signed sender execution-authority attestation bound to a UTT and
  accepted quote.
- ETK-R is signed receiver participation or eligibility evidence and cannot be
  fabricated merely by hashing ETK-S.
- Passive-credit and pre-authorized beneficiary flows do not falsely claim that
  a receiver actively confirmed.

## Files

- `docs/ADR-001-railone-pilot-baseline.md` - authoritative architecture decision.
- `railone_crypto/canonical_json.py` - strict deterministic JSON encoding.
- `railone_crypto/key_provider.py` - key metadata and signer/registry contracts.
- `railone_crypto/signature_service.py` - signed artifact envelopes and verification.
- `tests/test_signature_service.py` - deterministic, tamper, purpose, lifecycle,
  and serialization tests.
- `railone_identity/` - deterministic continuity and attestation validation.
- `railone_authority/` - signed ETK-S and ETK-R issuance.
- `tests/test_identity_continuity.py` - identity and attestation tests.
- `tests/test_execution_authority.py` - ETK binding and participation tests.

## Run the tests

From this directory:

```bash
python run_tests.py
```

The runner resolves the project root automatically, so it may also be invoked
with an absolute path from PowerShell.

The implementation uses the already-pinned `cryptography` package.

## Integration rule

Do not connect this batch to the legacy `crypto/keys/*.json` files. Those keys
were present in the uploaded repository snapshot and must be treated as
compromised. Production integration must supply a `SigningKeyProvider` backed
by an isolated signer, HSM, KMS-compatible service, or Vault-like service.

The in-memory signing and continuity-secret providers are explicitly test-only.
Production adapters must use isolated key services and a durable repository with
a unique constraint on the keyed identity fingerprint.

Step 03 will use these verified identity and authority artifacts when it
introduces quote acceptance and immutable UTT creation.
