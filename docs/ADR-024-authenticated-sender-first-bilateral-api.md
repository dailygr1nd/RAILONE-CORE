# ADR-024 — Authenticated Sender-First P2P API (Sandbox)

**Status:** Implemented in the proposed patch; local tests validated; durable PostgreSQL end-to-end gate still required.
**Depends on:** ADR-023 sender-first ETK-S → ETK-R → UTT, the existing API audit/auth guard, and migrations 0001–0016.

## Decision

Expose the **already independently signed** sender and receiver authorizations through the existing authenticated API boundary. RailOne validates, but does **not** sign a human user's ETK-S or ETK-R just because the caller presents a token or key name.

1. `POST /v1/bilateral/p2p/etk-s/verify` — sender's `HUMAN` token with `continuity_uid` matching `signed_quote.payload.payer.actor_id`; verifies quote and ETK-S signature/ownership/terms/expiry.
2. `POST /v1/bilateral/p2p/etk-r/verify` — receiver's `HUMAN` token with `continuity_uid` matching beneficiary; verifies quote, ETK-S, ETK-R and the exact ETK-S digest binding.
3. `POST /v1/bilateral/p2p/utts` — sender's scoped token, `Idempotency-Key` header, complete signed quote/ETK-S/ETK-R and `origin_intent_id`; verifies again and calls **strict** `QuoteAcceptanceService.accept` to atomically persist UTT v3 plus both ETK authorities.

The two `/verify` calls are **stateless preflight checks**: they do *not* write an ETK inbox or imply that RailOne holds consent pending later finalization. The receiver's external client obtains the quote and ETK-S from a client/institutional channel, signs ETK-R independently, then returns that signed envelope. A shared pending-authorization inbox, secure relay service, signed quote issuance APIs, delegated institutional principals, and production participant identity provisioning are **not included** in this slice.

## Request shapes

Both `/verify` operations accept a JSON object containing `signed_quote`, `sender_authority`, and (for ETK-R) `receiver_authority`. Each signed object uses the existing `SignatureEnvelope` JSON shape:

```json
{
  "protected": {"...": "versioned signing header from the client"},
  "payload": {"...": "signed canonical RailOne artifact"},
  "signature": "<base64url Ed25519 signature>"
}
```

UTT creation example (all three artifact objects are complete signed envelopes):

```http
POST /v1/bilateral/p2p/utts
Authorization: Bearer <sender short-lived access token>
Idempotency-Key: IDEM-P2P-CLIENT-0001
X-Request-ID: REQ-P2P-CLIENT-0001
Content-Type: application/json

{
  "signed_quote": {"protected": {}, "payload": {}, "signature": "..."},
  "sender_authority": {"protected": {}, "payload": {}, "signature": "..."},
  "receiver_authority": {"protected": {}, "payload": {}, "signature": "..."},
  "origin_intent_id": "MOBILE-REQUEST-0001"
}
```

The empty objects above are **shape placeholders**, not valid signed artifacts. Real signatures must be constructed by independent, authorized signing clients following the existing canonical signing contract.

Successful response:

```json
{
  "status": "ACCEPTED", "authority_version": 3,
  "quote_id": "QUOTE-...", "utt_id": "UTT-...", "replayed": false
}
```

Preflight responses indicate `persisted: false`. The final response identifies the atomically persisted UTT. Idempotent replay of the exact same payload and idempotency key returns the original UTT with `replayed: true`; the same key with changed request material responds 409.

## Security rules

- API routes are **opt-in**. If `RailOneApiFacade` is not injected with `BilateralP2PApi`, the three routes are absent (404).
- The API requires `PrincipalType.HUMAN`, normalized scoped `continuity_uid`, and actor/role matching on all three operations. Even a partner service or operator token cannot impersonate a P2P user. A future delegation model requires a separate ADR and conformance suite.
- RailOne verifies the existing signed ETK cryptographic chain, not arbitrary caller-provided claims. No `signing_key_id` shortcut is accepted.
- Inputs are bounded to 32 KiB canonical JSON per operation. The idempotency key is constrained to 8–128 safe characters; the origin intent ID is caller-provided but bounded and not accepted as an actor identity.
- Authentication, per-route rate limiting and signed API request auditing are enforced through `AuthenticatedRequestGuard`. Each audit event has a unique nonce so repeated request IDs in the same second do not collide. HTTP 409 conflicts are also audited as denied, not logged as internal server errors.
- HTTP errors are generic; no full beneficiary account references, bearer tokens, ETK bodies, private keys or signed payloads are written to the API audit record.
- PostgreSQL deployed sandbox composition uses `DeployedSandboxRuntime.authenticated_p2p_facade`, which wires `PostgresRateLimitStore`, `PostgresApiAuditStore`, `PostgresContractStore`, and the strict v3 acceptance path. The provided `AccessTokenService` must be configured with a **durable** token revocation store and trusted issuer/keys; the factory does not provision those dependencies.
- The existing downstream ExecutionPlan/RTT checks, signed dispatch wrappers, and economic effect fences remain unchanged.

## Sandbox composition

```python
# Assuming `runtime` was built by compose_deployed_sandbox and migrations
# 0001–0016 were already applied to an explicitly disposable database:
from railone_api.http import create_app

facade = runtime.authenticated_p2p_facade(
    signatures=trusted_signatures,  # trusted ETK, quote, UTT verifier/signing provider
    access_tokens=trusted_access_token_service,  # use PostgresTokenRevocationStore
    utt_signing_key_id="<core UTT signing key ID>",
    authority_signing_key_id="<legacy signer compatibility key ID>",
    api_audit_signing_key_id="<core API audit signer ID>",
)
app = create_app(facade=facade, expose_docs=False)
```

The values in angle brackets are placeholders, not real key material. Do not use the local in-memory demo signing provider to serve institution-controlled funds.

## Validation

```powershell
python -m unittest -v tests.test_authenticated_bilateral_api
python -m unittest -v tests.test_compromised_institution_harness
python run_tests.py
```

For live PostgreSQL, use the existing **disposable-only** `RAILONE_TEST_DATABASE_URL`, `RAILONE_ALLOW_TEST_SCHEMA_RESET=1`, and `RAILONE_REQUIRE_LIVE_POSTGRES=1` gates. The 0016 migration is a prerequisite. This patch introduces **no new SQL migration**.

The API-created UTT is tested in-memory through `ExecutionPlanningService.build_plan` and `RttAttemptService.start_next`, in addition to HTTP authorization negative tests. An external HTTP-to-PostgreSQL-to-dispatch end-to-end test against your running Docker container remains a release gate. This API patch is **not** a live-funds authorization or a production FAPI profile.
