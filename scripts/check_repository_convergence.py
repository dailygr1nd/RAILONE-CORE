"""Validate that RailOne has one clean authoritative pilot runtime."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PACKAGES = {
    "railone_api",
    "railone_authority",
    "railone_callbacks",
    "railone_contracts",
    "railone_crypto",
    "railone_execution",
    "railone_history",
    "railone_identity",
    "railone_institutions",
    "railone_notifications",
    "railone_operations",
    "railone_partners",
    "railone_postgres",
    "railone_projection",
    "railone_providers",
    "railone_sandbox",
    "railone_security",
}
LEGACY_ROOTS = {
    "adapters",
    "compliance",
    "crypto",
    "execution",
    "idempotency",
    "identity",
    "institutions",
    "keys",
    "ledger",
    "revenue",
    "routing",
    "settlement",
    "webhooks",
}
GENERATED_NAMES = {
    ".coverage",
    ".pytest_cache",
    "__pycache__",
    "desktop.ini",
}
EXPECTED_MIGRATIONS = [
    "0001_identity_transaction_history.sql",
    "0002_execution_provider_outbox.sql",
    "0003_postgres_runtime_projection.sql",
    "0004_authenticated_api_security.sql",
    "0005_mpesa_callback_reconciliation.sql",
    "0006_partner_bindings_settlement_notifications.sql",
    "0007_encrypted_vault_sandbox_runtime.sql",
    "0008_deployable_sandbox_workers.sql",
    "0009_institution_adapter_spi.sql",
]


def validate() -> list[str]:
    errors: list[str] = []
    present = {path.name for path in ROOT.iterdir() if path.is_dir()}

    missing = sorted(REQUIRED_PACKAGES - present)
    if missing:
        errors.append(f"missing authoritative packages: {', '.join(missing)}")

    legacy = sorted(LEGACY_ROOTS & present)
    if legacy:
        errors.append(f"legacy root packages remain: {', '.join(legacy)}")

    step_directories = sorted(
        path.name
        for path in ROOT.iterdir()
        if path.is_dir() and re.fullmatch(r"step_\d{2}_.+", path.name)
    )
    if step_directories:
        errors.append(f"cumulative step directories remain: {', '.join(step_directories)}")

    for path in ROOT.rglob("*"):
        if path.name in GENERATED_NAMES or path.suffix == ".pyc":
            errors.append(f"generated artifact present: {path.relative_to(ROOT)}")
        if path.is_dir() and path.name.endswith(".egg-info"):
            errors.append(f"packaging artifact present: {path.relative_to(ROOT)}")

    migrations = sorted(path.name for path in (ROOT / "migrations").glob("*.sql"))
    if migrations != EXPECTED_MIGRATIONS:
        errors.append(
            "migration chain differs from immutable 0001-0009 baseline: "
            + ", ".join(migrations)
        )

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if 'name = "railone-core"' not in pyproject or 'version = "0.14.0"' not in pyproject:
        errors.append("pyproject does not identify the converged 0.14.0 package")

    required_files = {
        ".gitignore",
        "README.md",
        "SECURITY.md",
        "STEP_10_RELEASE_MANIFEST.md",
        "STEP_11_RELEASE_MANIFEST.md",
        "STEP_11B_RELEASE_MANIFEST.md",
        "STEP_11C_RELEASE_MANIFEST.md",
        "STEP_11D_RELEASE_MANIFEST.md",
        "run_tests.py",
    }
    absent_files = sorted(name for name in required_files if not (ROOT / name).is_file())
    if absent_files:
        errors.append(f"required root files missing: {', '.join(absent_files)}")

    if (ROOT / "STEP_09_RELEASE_MANIFEST.md").exists():
        errors.append("superseded Step 09 release manifest remains at repository root")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Repository convergence check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Repository convergence check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
