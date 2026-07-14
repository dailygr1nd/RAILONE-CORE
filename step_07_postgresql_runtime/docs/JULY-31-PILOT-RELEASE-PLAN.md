# RailOne July 31, 2026 Pilot Release Plan

## Target

Deliver a credible pilot release candidate by July 31, 2026. The target is a
controlled sandbox or low-risk pilot, not unrestricted production traffic.

## Frozen pilot scope

- One corridor and currency pair.
- One provider sandbox adapter with documented idempotency behavior.
- P2P sender-to-beneficiary flow.
- One Avia merchant-context flow: supplier payment or branch fund transfer.
- Quote → acceptance → UTT → ExecutionPlan → RTT → provider submission →
  normalized outcome → reconciliation/settlement evidence.
- ContUID and exact-UTT transaction-history reads.
- No custody, wallets, payroll, lending, ERP expansion, or AI-authorized routing.

## Schedule

| Dates | Required outcome |
|---|---|
| July 14–17 | PostgreSQL adapters, migrations, transaction boundaries, outbox and idempotency |
| July 18–21 | Authenticated APIs, token-derived actor scope, rate limits, request audit |
| July 22–25 | One provider sandbox adapter, callback inbox, normalized outcomes, reconciliation |
| July 26–28 | Metrics, tracing, structured logs, alerts, secret rotation and backup/restore drill |
| July 29–30 | Concurrency, replay, timeout, duplicate callback and provider-failure drills |
| July 31 | Release-candidate demo, evidence pack, go/no-go review and rollback rehearsal |

## Pilot release gates

All gates are mandatory:

- 100% passing unit and integration suite.
- PostgreSQL migration tested from empty database and previous pilot version.
- No private signing or continuity keys in source, images, logs, or database.
- Stable idempotency at quote acceptance, RTT creation, provider submission,
  callback ingestion, and event consumption.
- Unknown provider outcome always blocks another route until reconciliation.
- Authenticated actor scope proven for ContUID, merchant, branch, partner and
  operator access; both denied and privileged reads audited.
- Signed UTT, RTT, ETK and execution-event verification exercised end to end.
- Backup restore, worker crash, expired lease, broker outage and database
  restart drills completed.
- No customer balance or held-funds model anywhere in RailOne or Avia.
- One-click pilot deployment and rollback instructions validated on a clean host.

## Production-grade gates after the prototype

Unrestricted production additionally requires independent security review,
provider certification, privacy and retention review, key-management/HSM
integration, sustained load testing, on-call ownership, incident response,
multi-zone recovery objectives, and operating history from the controlled
pilot. The July prototype must not be marketed as having passed these later
gates.
