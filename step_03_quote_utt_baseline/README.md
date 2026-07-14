# RailOne Pilot Convergence - Step 03

This cumulative batch contains the cryptographic, identity, and execution-
authority baselines and adds RailOne's commercial-contract boundary: signed
quotes, explicit quote acceptance, and exactly-once immutable UTT creation.

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
- A quote is a signed, expiring commercial offer and does not bind execution to
  a specific rail.
- A UTT can only be created after explicit acceptance of a valid quote.
- Quote acceptance creates the UTT and ETK-S as one atomic contract record.
- One accepted quote cannot produce multiple UTTs.
- Idempotency-key reuse with different request material is rejected.
- UTT commercial payloads and signed envelopes are deeply immutable in memory.
- Customer pricing is `PER_INTENT`, preserving one charge across all future RTT
  attempts.

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
- `railone_contracts/` - quote, origin-context, acceptance, UTT, and store contracts.
- `tests/test_quote_acceptance.py` - quote and UTT invariant tests.

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

Step 04 will persist ExecutionPlans and create the first RTT only after the UTT
existence guard succeeds.
