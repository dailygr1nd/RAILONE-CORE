# RailOne v0.17 — HTTP institutional sandbox manifest timestamp hotfix

## Cause

The three v0.17 live PostgreSQL scenarios use a fresh sandbox `fixture.sandbox_now` containing sub-second precision. The reference manifest sets `issued_at` to that timestamp, while the signature header stores `iat` as integral Unix seconds. Since the verifier requires `manifest.issued_at <= signature_iat < manifest.expires_at`, the signature appears to predate the validity window by less than one second.

This is a test-fixture precision mismatch; do not relax or disable `CapabilityManifestSigner.verify` or `SENDER_FIRST_BILATERAL_V3_REQUIRED`.

## Change

Only `tests/institutional_live_support.py` changes. In the `if http_bilateral:` block the synthetic fixture timestamp is normalized to whole UTC seconds:

```python
fixture.sandbox_now = (datetime.now(timezone.utc) - timedelta(seconds=10)).replace(
    microsecond=0,
)
```

This applies only to the in-process HTTP sandbox test path. No changes to production manifest verification, authorization, or dispatch are made; no migration is required.

## Apply

Apply **after** the v0.17 HTTP-to-PostgreSQL E2E patch, from the repository root and your current v0.17 feature branch:

```powershell
git status --short
git apply --check .\RailOne_v0.17_manifest_timestamp_hotfix.patch
git apply .\RailOne_v0.17_manifest_timestamp_hotfix.patch
```

If you have uncommitted changes to the same file, review the diff before applying. Never apply this to a branch that lacks the earlier v0.17 E2E changes.

## Validate

Use **only your disposable** PostgreSQL database; live tests reset schemas.

```powershell
docker start railone-pg-disposable
$env:RAILONE_TEST_DATABASE_URL = "postgresql://railone_test:railone_test@localhost:55432/railone_test"
$env:RAILONE_ALLOW_TEST_SCHEMA_RESET = "1"
$env:RAILONE_REQUIRE_LIVE_POSTGRES = "1"
python -m unittest -v tests.test_postgres_live.LivePostgresRuntimeTests.test_v017_http_to_postgres_institutional_dispatch
python -m unittest -v tests.test_postgres_live.LivePostgresRuntimeTests.test_v017_http_to_postgres_timeout_preserves_fence
python -m unittest -v tests.test_postgres_live.LivePostgresRuntimeTests.test_v017_http_to_postgres_crash_preserves_fence
python run_tests.py
```

All the above tests are intended to pass with **no skipped tests** when the database and optional dependencies are available. The expected discovery count remains 292 because this patch adds no tests. Run demos only after the full suite passes.

## Validation performed here

- Patch applies cleanly against the file in the previous v0.17 E2E bundle.
- Corrected file passes Python compilation.
- Reproduced actual `CapabilityManifestSigner.verify`: a fractional-second synthetic issued_at is rejected; an otherwise identical whole-second timestamp is accepted.
- Could not run the live PostgreSQL suite in this environment, so its outcome is not yet verified.
