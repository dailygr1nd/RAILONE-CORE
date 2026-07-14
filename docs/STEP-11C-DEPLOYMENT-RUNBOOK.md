# Step 11C deployable sandbox runbook

## Boundary

This profile is for shared synthetic integration only. It rejects non-synthetic
provider endpoints and does not authorize live funds, real customer data or
production partner credentials.

## Required configuration

Inject the following as deployment configuration or secret references:

- `RAILONE_RUNTIME_MODE=SIMULATED_PILOT`
- `RAILONE_DATABASE_URL`
- `RAILONE_MIGRATIONS_DIRECTORY`
- `RAILONE_SANDBOX_EFFECT_WORKER_ID`
- `RAILONE_ACCOUNT_ENDPOINT_KEK_ID`
- `RAILONE_CONTACT_DESTINATION_KEK_ID`
- `RAILONE_PROVIDER_CREDENTIAL_KEK_ID`
- `RAILONE_NOTIFICATION_BODY_KEK_ID`

KEK identifiers are configuration; KEK bytes are not. The application must be
given an authenticated `IsolatedKeyServiceClient` backed by an approved KMS/HSM.
Provider credential records should use versioned references such as
`consumer_secret:v2`; rotate by writing a new immutable record and changing the
injected credential-reference mapping, never by overwriting the old envelope.

## Startup order

1. Build `DeployedSandboxConfig` and validate it.
2. Create the isolated key-service and PostgreSQL connection factories.
3. Call `compose_deployed_sandbox(...)` with the effect consumer.
4. Acquire the deployment migration lock and call `runtime.apply_migrations()`.
5. Register only `SIM-` endpoints and synthetic encrypted credentials.
6. Confirm `runtime.readiness()["status"] == "READY"`.
7. Start the external process loop and call `runtime.supervisor.tick()` once per
   scheduled interval.

The composition does not create signing keys. Supply the previously defined
isolated Ed25519 signer when wiring quote, UTT, RTT, settlement and API services.

## Worker recovery

- A worker claim owns an effect only until `lease_until_tick`.
- A restarted worker advances the durable clock and reclaims expired leases.
- A stale worker cannot mark a reclaimed effect delivered.
- A consumer exception reschedules the same immutable effect id.
- The configured attempt cap moves repeated failures to `DEAD_LETTER`.
- Dead letters require reconciliation and an audited operator decision.

## Data checks

Before shared sandbox traffic, verify:

- `sms_notification_outbox.rendered_body` is `[ENCRYPTED]` for new rows;
- every new SMS row contains a `NOTIFICATION_BODY` envelope;
- provider secrets exist only under `PROVIDER_CREDENTIAL` envelopes;
- logs contain no plaintext body, MSISDN, account endpoint, token or credential;
- the latest migration is `0008`; and
- all provider references used by effect simulation begin with `SIM-`.

## Release gates

Run:

```powershell
python -m pip install -e ".[pilot]"
python .\scripts\check_repository_convergence.py
python .\scripts\check_no_secrets.py
python .\run_tests.py
```

CI must execute the HTTP and disposable PostgreSQL tests with zero skips before
deployment. Test database reset flags must never target a shared database.
