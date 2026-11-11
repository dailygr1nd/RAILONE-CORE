# RailOne v0.16 — Authenticated Sender-First Bilateral P2P API Patch

## Patch base

Apply **only after** the corrected sender-first v3 patch and PostgreSQL hotfix from the previous steps. This patch is based on that exact corrected/hotfixed file tree. **Do not apply the superseded receiver-first patch.**

New endpoint shape:

- `POST /v1/bilateral/p2p/etk-s/verify` (sender bearer token)
- `POST /v1/bilateral/p2p/etk-r/verify` (receiver bearer token)
- `POST /v1/bilateral/p2p/utts` (sender bearer token + `Idempotency-Key`)

Both ETK preflight endpoints verify independently signed artifacts; they do **not** persist a pending acceptance. The third endpoint persistently creates a UTT and its ETK-S/ETK-R records through the existing quote acceptance store. **RailOne never signs ETKs for the payer/beneficiary at these HTTP endpoints.**

## Apply in PowerShell

From the clean branch containing the sender-first v3 patch and prior test hotfix:

```powershell
git switch -c feat/authenticated-bilateral-p2p-api
git apply --check .\RailOne_v0.16_authenticated_bilateral_api.patch
git apply .\RailOne_v0.16_authenticated_bilateral_api.patch
python -m pip install -e ".[pilot]"
python -m unittest -v tests.test_authenticated_bilateral_api
python run_tests.py
```

## Live PostgreSQL gate — disposable DB only

```powershell
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
python run_tests.py
```

These settings permit destructive schema resets and must **never** be used with a shared or production database. A successful local test run without these variables skips the live PostgreSQL integration suite.

## Verification and operational scope

- Strict sender-first ETK-S → ETK-R → UTT v3 remains enforced.
- API authorization uses trusted token `continuity_uid` scopes, human-principal type, and independently signed ETKs.
- Signed audit logging handles repeated request IDs without collisions; idempotency conflicts return HTTP 409 and are recorded as denied.
- Existing noncustodial economic-effect fencing, institutional admission, and dispatch wrappers are left untouched.
- New API routes appear only when explicitly wired. See `docs/ADR-024-authenticated-sender-first-bilateral-api.md` for an example of composing the API with PostgreSQL-backed services.
- Future work: pending ETK relay/inbox, independent institution/identity provisioning, external signer integration, audited key rotation, production auth/FAPI profile, live HTTP/PostgreSQL/RTT/dispatch validation.

**Locally validated:** Python suite; **not locally validated:** disposable PostgreSQL because no live DB server/psycopg was available in the packaging environment.

Suggested commit message: `feat(api): enforce sender-first bilateral P2P acceptance via authenticated endpoints`
