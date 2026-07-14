# ADR-009: M-PESA Kenya sandbox execution boundary

- Status: Accepted for the controlled pilot baseline
- Date: July 14, 2026
- Scope: Kenya domestic KES, Safaricom Daraja B2C sandbox

## Decision

RailOne's first concrete provider boundary is `MPESA-KE`, using the Daraja B2C
sandbox for whole-KES mobile-money disbursements. It supports the frozen pilot's
P2P beneficiary flow and Avia merchant-context supplier or branch-payment
intent. RailOne consumes an already-authorized intention, creates an immutable
UTT and RTT lineage, and asks M-PESA to execute it. RailOne never holds a user
balance or represents M-PESA funds as its own.

The default adapter path is sandbox-shaped and configurable. The exact B2C API
version, product entitlement, initiator credential, shortcode, callback schema,
and production URL must be confirmed inside the authenticated Daraja application
before any traffic. The public Daraja portal describes sandbox application and
API testing but is not provider certification for this implementation:
<https://developer.safaricom.co.ke/>.

## Submission semantics

- OAuth is acquired before the payment endpoint is called. A failed OAuth call
  is therefore a known retryable pre-dispatch failure.
- The B2C request accepts only `MOBILE_MONEY`, KES-to-KES, equal send/receive
  amounts, whole KES, and normalized Kenyan MSISDNs.
- Secrets are loaded through a credential-provider boundary and are hidden from
  object representations. Production must replace environment variables with
  a secrets manager and controlled rotation.
- The provider's immediate `ResponseCode=0` means accepted for asynchronous
  processing. It is not success, settlement, or beneficiary credit.
- `ConversationID`, `OriginatorConversationID`, and the expected amount are
  persisted as correlation context. Account references are not emitted into
  signed operational events.
- The adapter declares `supports_idempotency = False`. Daraja B2C is not assumed
  to provide a RailOne-verifiable idempotency guarantee. If a worker restarts
  from `DISPATCHING`, RailOne records an unknown outcome and makes no second
  provider call.

## Callback and finality semantics

The public callback ingress and the internal RailOne callback processor are two
different trust boundaries. The processor verifies an HMAC placed over the raw
body by RailOne's trusted ingress gateway. This HMAC is explicitly not described
as a native Safaricom signature.

The gateway must terminate TLS, cap the request body, remove any caller-supplied
internal signature header, enforce the provider connectivity policy available
for the contracted integration, and add a fresh internal HMAC only on the
private hop to RailOne. Until Safaricom confirms a stronger native callback
authentication method or private connectivity, the callback is provider-reported
execution evidence under the gateway policy—not independent cryptographic proof
from Safaricom.

Before changing an RTT, RailOne requires all of the following:

- a valid internal ingress HMAC;
- a known provider `ConversationID`;
- the stored `OriginatorConversationID`;
- an allowlisted, size-bounded callback shape;
- for success, a non-empty `TransactionID`;
- a `TransactionAmount` equal to the dispatched amount; and
- when supplied, a `TransactionReceipt` equal to `TransactionID`.

Only normalized allowlisted fields are placed in the callback inbox. The same
provider event identifier with the same material is idempotent; reuse with
different material is a conflict. Malformed, uncorrelated, or amount-mismatched
callbacks do not occupy the canonical event identifier.

A queue timeout moves the RTT and plan to `RECONCILIATION_REQUIRED`. It never
opens another route. A later correlated success may resolve that RTT to
`SUCCEEDED` and finalize the plan. A correlated non-zero result resolves to an
explicit terminal failure unless a reviewed result-code policy marks that code
retryable. The default policy marks no provider code retryable.

## Operational gates

This step is a sandbox-capable prototype, not a claim of production approval.
Before pilot traffic, RailOne must complete:

1. authenticated Daraja contract/schema review and sandbox certification;
2. disposable PostgreSQL migration, rollback, duplicate, and concurrency tests;
3. callback gateway deployment with header stripping, network policy, HMAC
   rotation, rate limits, and request-size limits;
4. a reconciliation runbook for timeouts, unknown dispatches, and late results;
5. secrets-manager wiring and initiator/security-credential rotation;
6. dashboards and alerts for OAuth failures, unknown outcomes, callback rejects,
   reconciliation age, and unmatched provider references; and
7. legal, privacy, retention, provider, and security review.

No second provider, cross-border corridor, payroll product, or custodial balance
is added in this decision.
