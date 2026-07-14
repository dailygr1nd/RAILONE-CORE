# Step 11D release manifest

- Build date: July 14, 2026
- Package version: 0.14.0
- Custody model: non-custodial
- Signature baseline: Ed25519 signed adapter capability manifests
- Confidentiality baseline: TLS in transit; AES-256-GCM envelopes at rest
- Adapter binding: exact `adapter_id@semantic-version` per RTT
- Migration chain: immutable `0001` through `0009`
- Runtime restriction: simulated integration pilot; no live funds

## Added controls

- institution adapter SPI for submit, status, reconciliation, callback and health;
- Ed25519-signed, expiring capability manifests and deterministic registry;
- exact adapter-version pinning carried in provider execution requests;
- explicit accepted, retryable rejection, terminal rejection and unknown outcomes;
- finality levels that prevent submission acceptance from claiming settlement;
- hardened HTTPS transport with TLS context injection, size limits and timeouts;
- sandbox-only no-auth, bearer-token and proof-of-possession auth boundaries;
- canonical JSON and deterministic ISO 20022 pain.001.001.09 pilot codecs;
- configurable HTTP adapter with explicit code normalization;
- domestic bank, instant-switch and cross-border synthetic reference profiles;
- reusable adapter conformance checks;
- append-only manifest, RTT binding, normalized evidence and conformance tables;
- PostgreSQL signed-manifest store; and
- ADR-013 and Step 11D institution onboarding runbook.

## Important qualification

The ISO 20022 codec is a RailOne pilot profile, not proof of scheme or partner
certification. The domestic-switch and cross-border profiles are synthetic
reference shapes and do not claim connection to PesaLink, Thunes or any other
named institution.

## Verification result

- Tests discovered: 146
- Tests passed with HTTP dependencies installed: 143
- Environment-gated tests skipped: 3 disposable PostgreSQL tests
- Repository convergence check: passed
- Repository secret check: passed
- Archive SHA-256: supplied alongside the release artifact

## Production blockers retained

- partner-specific API/message mapping and bilateral certification;
- externally operated Ed25519 HSM/KMS signer and certificate lifecycle;
- callback authentication tailored to each partner;
- production mTLS/OAuth/FAPI credentials and trust anchors;
- corridor policy, sanctions/AML responsibilities and regulatory approvals;
- reconciliation files/status APIs, dispute procedures and operational SLAs;
- load, failover, restore, chaos and independent security testing.
