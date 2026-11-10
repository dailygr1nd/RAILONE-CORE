# RailOne v0.16 Alpha — Phase 4: Institutional Sandbox Admission

## Baseline

Apply **after** Phase 3 (ADR-018 / migration 0013). This is a source-only control extension:
**no migration 0014 yet**. The patch was built and clean-applied against the
v0.15.1 + Phase 1 + Phase 2 + Phase 3 baseline in the supplied snapshot.

## Scope

- Adds `railone_institutions/admission.py` with a trusted gateway protocol.
- Revalidates exact signed and active adapter manifests at admission.
- Adds `INSTITUTIONAL_SANDBOX` coordinator mode requiring the admission gate.
- Rejects caller-selected adapters and public provider-ready `prepare()` in this mode.
- Verifies the persisted signed wrapper against a trusted core snapshot and
  the prepared provider request, including idempotency, amount, provider and adapter.
- Requires a separate, authoritative economic-effect fence decision before dispatch.
- Preserves `SIMULATED_PILOT` mode for existing tests and synthetic demonstrations.
- Rejects production/live dispatch modes. **NOT live-funds ready.**

## What is NOT implemented

No production-grade snapshot reader, SQL-backed economic fence authorization,
license enforcement, or distributed dispatch reservation. Mock/fixture readers
in tests are not permission to connect real funds. Existing PostgreSQL tests
remain environment-gated.

## Windows PowerShell application

From your repository root after completing and committing Phase 3:

```powershell
git status --short
git switch feat/v0.16-signed-dispatch-wrapper
git pull --ff-only origin feat/v0.16-signed-dispatch-wrapper
git switch -c feat/v0.16-institutional-admission
```

Place `RailOne_v0.16.0_phase4_trusted_admission.patch` in the root.

```powershell
git apply --check .\RailOne_v0.16.0_phase4_trusted_admission.patch
git apply .\RailOne_v0.16.0_phase4_trusted_admission.patch
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest tests.test_institution_admission_gateway -v
python run_tests.py
python scripts/check_repository_convergence.py
python scripts/check_no_secrets.py
git diff --check
```

Expected on the supplied baseline: **222 tests total, 219 passed, 3 skipped**.
The skipped tests need disposable PostgreSQL configuration. Do not assume the
same results for a divergent working branch until tests run there.

```powershell
git add railone_operations/service.py railone_institutions/registry.py railone_institutions/__init__.py
git add railone_institutions/admission.py docs/ADR-019-trusted-institutional-dispatch-admission.md
git add tests/test_institution_admission_gateway.py
git diff --cached --check
git commit -m "feat(institutions): enforce sandbox admission before dispatch"
git push -u origin feat/v0.16-institutional-admission
```

If the branch already exists, `git switch feat/v0.16-institutional-admission`
instead of `git switch -c`. If the patch check fails, **do not force it**;
inspect `git status` and compare with the forthcoming latest repository snapshot.

## Key review items

- Security review of `AuthoritativeSnapshotReader` and `EconomicEffectFenceReader`
  implementations when wired to trusted SQL stores.
- Atomic dispatch authorization / concurrent workers and crash recovery.
- Partner cert and contract authority gates; license checks in Phase 5.
- No institutional real-money endpoints until all gates pass.
