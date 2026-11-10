# RailOne v0.16.0 Alpha — Currency & Settlement Instrument Registry

## What this patch does

This **additive development patch** introduces a descriptive currency registry and settlement instrument profiles for commercial-bank money, regulated e-money, retail CBDC and wholesale CBDC. It does **not** enable CBDC payments, change UTT/RTT execution, authorize any new route, or touch existing migrations 0001–0010.

**Files created:**
- `railone_currency/__init__.py`
- `railone_currency/models.py`
- `railone_currency/registry.py`
- `migrations/0011_currency_and_settlement_instruments.sql`
- `tests/test_currency_instruments.py`
- `docs/ADR-016-currency-and-settlement-instruments.md`

**File modified:** `scripts/check_repository_convergence.py` (adds new package and migration to the allowed authoritative set).

## Apply on Windows, in the RailOne repository root

```powershell
# First ensure your branch exists and is current with main.
git switch feat/v0.16-currency-settlement-policy
git status
git merge --ff-only main

# Copy RailOne_v0.16.0_currency_instruments_0011.patch to your repo root.
git apply --check .\RailOne_v0.16.0_currency_instruments_0011.patch
# Only if --check succeeds:
git apply .\RailOne_v0.16.0_currency_instruments_0011.patch

git diff --stat
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest tests.test_currency_instruments -v
python run_tests.py
python scripts/check_no_secrets.py
python scripts/check_repository_convergence.py
git diff --check

# Stage ONLY the seven intended files; no repo archives or local secrets.
git add railone_currency/ migrations/0011_currency_and_settlement_instruments.sql tests/test_currency_instruments.py docs/ADR-016-currency-and-settlement-instruments.md scripts/check_repository_convergence.py
git commit -m "feat(currency): add passive sovereign and CBDC settlement reference registry"
git push -u origin feat/v0.16-currency-settlement-policy
```

**If `git merge --ff-only main` fails**, STOP: the branch has diverged and must be inspected before merging. Do not force-reset or delete commits.

**If `git apply --check` fails**, STOP: the patch is based on the supplied v0.15.0 source snapshot and may not match newer edits; do not force apply. Inspect existing files first.

**If no new changes are shown**, avoid making an empty commit.

## Validation performed in the authoring environment

- Git patch applies cleanly to the reconstructed v0.15 source snapshot.
- Full suite: 177 discovered, 174 passed, 3 skipped; 0 failures/errors.
- 18 new currency and instrument unit tests passed.
- Secret check passed.
- Repository convergence check passed when run in a simulated clean authoritative tree with old `step_*` historical snapshots excluded; your actual Git checkout should be verified separately.
- PostgreSQL migration `0011` is supplied but was **not tested against a live PostgreSQL server** here. The skipped PostgreSQL tests must be exercised against a disposable DB before approving this migration for deployment.

## Commercial and legal guardrails

Currency codes are syntax-validated only; they are not proof of sovereign currency status. A CBDC entry is an **administrative reference**, not permission to connect to the CBDC infrastructure. No execution path consumes these records yet. Cryptoassets and stablecoins are excluded from the settlement-instrument enum, but an approved currency reference source and governance process are still required to stop mislabeled codes from entering the trusted catalog.
