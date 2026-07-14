# RailOne Pilot Convergence - Step 01

This batch establishes RailOne's canonical cryptographic baseline before the
execution pipeline is rebuilt.

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

## Files

- `docs/ADR-001-railone-pilot-baseline.md` - authoritative architecture decision.
- `railone_crypto/canonical_json.py` - strict deterministic JSON encoding.
- `railone_crypto/key_provider.py` - key metadata and signer/registry contracts.
- `railone_crypto/signature_service.py` - signed artifact envelopes and verification.
- `tests/test_signature_service.py` - deterministic, tamper, purpose, lifecycle,
  and serialization tests.

## Run the tests

From this directory:

```bash
python -m unittest discover -s tests -v
```

The implementation uses the already-pinned `cryptography` package.

## Integration rule

Do not connect this batch to the legacy `crypto/keys/*.json` files. Those keys
were present in the uploaded repository snapshot and must be treated as
compromised. Production integration must supply a `SigningKeyProvider` backed
by an isolated signer, HSM, KMS-compatible service, or Vault-like service.

The in-memory provider is explicitly test-only. Step 02 will use this signing
service when it introduces quote acceptance and immutable UTT creation.
