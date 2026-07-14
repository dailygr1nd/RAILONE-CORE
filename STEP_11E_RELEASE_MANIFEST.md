# Step 11E release manifest

- Build date: July 14, 2026
- Package version: 0.15.0
- Custody model: non-custodial
- Certification suite: `RAILONE-PARTNER-PILOT` v1.0.0
- Certification signature: Ed25519 through the isolated execution signer
- Adapter binding: exact `adapter_id@semantic-version`
- Migration chain: immutable `0001` through `0010`
- Runtime restriction: partner sandbox and synthetic pilot; no live funds

## Added controls

- canonical, content-addressed partner certification traces;
- capability-aware certification suite selection from signed manifests;
- 11 comprehensive reference scenarios covering P2P, merchant/supplier,
  cross-border, replay, uncertainty, callbacks, history, SMS and version pins;
- fail-closed trace ordering and exact-count assertions;
- verified evidence required before RTT success, plan finality or SMS creation;
- blind redispatch detection after unknown provider outcomes;
- metadata allowlisting to exclude credentials, raw endpoints and personal data;
- execution timeout enforcement and redacted driver failures;
- explicit separation of synthetic self-test and partner-sandbox evidence;
- authoritative coordinator requiring a verified active capability manifest;
- Ed25519-signed immutable certification reports;
- offline `railone-certify` CI command that emits unsigned drafts only;
- append-only PostgreSQL run, trace and report tables; and
- ADR-014 and Step 11E partner certification runbook.

## Qualification

A passing report demonstrates conformance to the declared RailOne sandbox suite.
It does not replace a partner contract, scheme certification, regulatory
approval, penetration test, production cutover review or live reconciliation
proof. Synthetic self-test results cannot be signed or persisted as partner
certification evidence.

## Verification result

- Tests discovered: 159
- Tests passed with HTTP dependencies installed: 156
- Environment-gated tests skipped: 3 disposable PostgreSQL tests
- Installed `railone-certify` command smoke test: passed
- Repository convergence check: passed
- Repository secret check: passed
- Archive SHA-256: supplied alongside the release artifact
