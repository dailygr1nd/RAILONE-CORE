# M-PESA sandbox runbook

This runbook prepares Step 09 for a controlled Daraja sandbox exercise. It does
not authorize production traffic.

## 1. Install and verify

From the Step 09 directory in PowerShell:

```powershell
python -m pip install -e ".[pilot]"
python .\run_tests.py
```

The bundled runner resolves the package root. Do not execute a nested test file
directly unless the editable package has already been installed.

## 2. Prepare PostgreSQL

Use a real secret from your local secret store, not a value committed to source:

```powershell
$env:RAILONE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/railone"
python .\migrate.py
```

Run the destructive integration suite only against a disposable database:

```powershell
$env:RAILONE_TEST_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
python .\run_tests.py
```

## 3. Obtain Daraja sandbox configuration

Create or select a sandbox application in the authenticated Safaricom Daraja
portal and confirm that B2C is enabled. Confirm the exact request path and
callback contract shown for that application; do not assume the source default
is the final contracted API version.

Supply these values at runtime through a secret manager or local environment:

```powershell
$env:RAILONE_MPESA_CONSUMER_KEY = "..."
$env:RAILONE_MPESA_CONSUMER_SECRET = "..."
$env:RAILONE_MPESA_INITIATOR_NAME = "..."
$env:RAILONE_MPESA_SECURITY_CREDENTIAL = "..."
$env:RAILONE_MPESA_SHORTCODE = "..."
$env:RAILONE_MPESA_INGRESS_HMAC_SECRET = "a-random-secret-of-at-least-32-bytes"
```

Never print these variables or place them in a checked-in `.env` file.

## 4. Deploy the callback ingress

Expose HTTPS result and timeout URLs at the gateway. The gateway must:

- reject bodies above 64 KiB;
- remove inbound `X-RailOne-Ingress-Signature` headers;
- enforce the agreed provider source/private-connectivity policy;
- compute `HMAC-SHA256(secret, raw_body)`;
- forward the value as `X-RailOne-Ingress-Signature: sha256=<hex>`; and
- forward only to RailOne's private callback endpoints.

Configure the B2C adapter with those public HTTPS URLs. RailOne exposes the
internal handlers only when an `MpesaCallbackProcessor` is explicitly passed to
`create_app`:

- `POST /v1/provider-callbacks/mpesa/result`
- `POST /v1/provider-callbacks/mpesa/timeout`

## 5. Execute the sandbox drill

Use one frozen KES amount and a provider-approved sandbox MSISDN. Verify this
state sequence:

1. accepted quote creates one immutable UTT;
2. the plan creates one signed RTT;
3. the provider submission enters `DISPATCHING` before the network call;
4. immediate Daraja acceptance becomes `ACCEPTED_FOR_PROCESSING` only;
5. a correlated result with matching transaction amount finalizes the RTT; and
6. the UTT/ContUID or merchant-context view reports the same execution lineage.

Then run negative drills: duplicate callback, changed duplicate, invalid HMAC,
amount mismatch, OAuth outage, transport timeout, queue timeout, late success,
and worker restart from `DISPATCHING`. The restart drill must make zero additional
B2C calls.

## 6. Go/no-go evidence

Capture test output, migration checksums, provider request/reference IDs with
secrets redacted, callback inbox records, reconciliation timing, logs, metrics,
and the rollback result. Any unknown provider outcome or unresolved callback
authentication question is a no-go for live funds.
