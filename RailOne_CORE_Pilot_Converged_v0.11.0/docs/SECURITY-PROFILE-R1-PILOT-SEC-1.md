# R1-PILOT-SEC-1

## Status

Required security profile for RailOne simulated pilot environments.

## Cryptographic roles

| Role | Required pilot primitive |
|---|---|
| RailOne artifact signatures | Ed25519 with versioned algorithm and key identifiers |
| Network protection | TLS 1.3 |
| Institutional service authentication | mTLS where the participant supports it |
| Sensitive data at rest | AES-256-GCM envelope encryption |
| ContUID derivation | HMAC-SHA-256 with a dedicated continuity key |
| Trusted callback ingress | HMAC-SHA-256 behind a controlled ingress gateway |
| Hash identifiers | SHA-256 with explicit domain separation where applicable |

Ed25519 provides authenticity and integrity. It does not provide
confidentiality and must not be described as encryption.

## Key profile

- Separate signing purposes for identity, quotes, execution, settlement,
  replay, access tokens, and API audit.
- Private signing operations occur through an isolated signer interface.
- No deployment private key is returned to application memory.
- Every key has `kid`, owner, purpose, algorithm, validity window, status, and
  rotation lineage.
- Revoked keys cannot sign or verify new operational artifacts.
- Historical verification policy is explicit and cannot reactivate authority.
- Sandbox keys are independently generated and cannot be promoted to
  production.

## API profile

- Short-lived access tokens with exact issuer and audience checks.
- Least-privilege ContUID, merchant, branch, partner, and operator scopes.
- Token revocation and atomic per-principal/route rate limits.
- Signed request audit without bearer-token or provider-credential material.
- Institution-facing APIs terminate behind TLS 1.3 and use sender-constrained
  authentication where available.
- FAPI 2.0 is the post-pilot institutional authorization target; the local
  development token issuer is not a FAPI authorization server.

## Data profile

- Pilot identities, accounts, balances, MSISDNs, and institutions are synthetic.
- UTTs contain opaque account-binding snapshots, never raw provider endpoints.
- Provider endpoint resolution occurs only inside the dispatch boundary.
- Contact destinations and provider endpoint records require envelope
  encryption before persistent sandbox use.
- Logs and traces use allowlists and never record tokens, credentials, raw
  endpoints, or unredacted callbacks.
- SMS bodies must remain privacy-safe and follow an approved retention window.

## Execution profile

Simulation changes economic effects, not security semantics. The pilot must use
the same:

- quote expiry and acceptance rules;
- UTT and RTT signature verification;
- idempotency and replay rejection;
- unknown-outcome blocking;
- callback correlation;
- reconciliation workflow;
- settlement-evidence requirement;
- notification finality gate; and
- audit and key-rotation behavior intended for production.

## Mandatory failure drills

1. Duplicate quote acceptance and changed idempotency material.
2. Provider timeout before and after request transmission.
3. Duplicate, delayed, reordered, malformed, and forged callbacks.
4. Callback worker crash between RTT update and inbox acknowledgement.
5. Revoked account binding immediately before RTT creation.
6. Outbox and SMS worker crash while state is `DISPATCHING`.
7. Settlement replay with changed provider evidence.
8. Key rotation, key revocation, database restore, and certificate expiry.

## Pilot release gate

The profile passes only when repository convergence and secret checks pass, all
tests run without skips, live disposable PostgreSQL tests pass, and no real
customer data or production credentials are present.
