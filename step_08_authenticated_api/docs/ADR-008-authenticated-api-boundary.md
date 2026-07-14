# ADR-008: Authenticated API and Actor-Scope Boundary

**Status:** Accepted for the controlled pilot  
**Date:** 2026-07-14

## Decision

RailOne API authority is derived only from a verified, short-lived Ed25519 JWT.
HTTP parameters and request bodies may select a resource, but they never grant
access to a ContUID, merchant, branch, partner, or operator scope.

Access tokens use a dedicated `ACCESS_TOKEN_SIGNING` key purpose. They contain
issuer, audience, subject, token ID, principal type, issue/not-before/expiry
times, and separate actor scopes. A token cannot outlive its signing key and the
pilot TTL is capped at 15 minutes by default. Revoked token IDs are stored
durably. RailOne exposes no public token-minting or bootstrap-owner route.

Human identity continuity and commercial scope remain separate:

- `continuity_uid` identifies a human continuity subject;
- `merchant_ids`, `branch_ids`, and `partner_ids` authorize commercial views;
- privileged transaction reads require `railone.transactions.read:any` plus an
  explicit access reason.
- `railone.transactions.read:any` may only appear on an `OPERATOR` principal.

Each authenticated principal and route template receives a fixed-window limit.
PostgreSQL applies increments atomically. Rate limiting is an abuse-control
boundary, not financial truth.

Every allowed, denied, rate-limited, and failed guarded request creates an
Ed25519-signed `railone.api_request_audit` artifact under a dedicated
`API_AUDIT_SIGNING` key. The audit omits bearer-token material and is append-only
in PostgreSQL. Domain-specific transaction-access audits continue to record the
target and privileged reason separately.

## HTTP surface

- `GET /healthz`
- `GET /v1/auth/me`
- `GET /v1/transactions/{utt_id}`
- `GET /v1/transactions?subject_kind=...&subject_id=...`
- `GET /v1/provider-submissions/{submission_id}`

Provider outcome access first proves access to the outcome's UTT. Provider
`ACCEPTED_FOR_PROCESSING` remains distinct from settlement success.
OpenAPI documentation is disabled by default and is enabled only by the gated
localhost development server.

## Consequences

The core authentication, authorization, rate-limit, and audit behavior is
transport-independent and tested without FastAPI. FastAPI/Uvicorn are optional
transport dependencies. PostgreSQL migration `0004` supplies revocation,
rate-limit, and audit tables.

Step 09 may add one provider sandbox adapter and callback verification. It must
reuse this boundary and may not accept actor scopes from provider or Avia
payloads as authorization truth.
