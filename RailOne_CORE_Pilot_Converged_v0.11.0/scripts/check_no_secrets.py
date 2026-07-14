"""Fail when repository files contain private key or credential material."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
FORBIDDEN_SUFFIXES = {
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
}
FORBIDDEN_PATH_PARTS = {
    ("crypto", "keys"),
    ("keys",),
}


def _private_boundaries() -> tuple[re.Pattern[str], ...]:
    private = "PRIVATE" + " KEY"
    openssh = "OPENSSH" + " PRIVATE"
    return (
        re.compile(r"-----BEGIN " + private + r"-----"),
        re.compile(r"-----BEGIN RSA " + private + r"-----"),
        re.compile(r"-----BEGIN EC " + private + r"-----"),
        re.compile(r"-----BEGIN " + openssh + r" KEY-----"),
    )


SENSITIVE_ASSIGNMENTS = (
    re.compile(
        r'(?i)["\']private_key["\']\s*:\s*["\'][A-Za-z0-9+/=_-]{32,}["\']'
    ),
    re.compile(
        r"(?i)(consumer_secret|client_secret|security_credential|api_key)\s*=\s*"
        r"[\"'](?!test|fake|dummy|example|change_me|consumer-secret|"
        r"encrypted-initiator-credential)[^\"'\n]{12,}[\"']"
    ),
)


def _ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in path.relative_to(ROOT).parts)


def _forbidden_path(path: Path) -> str | None:
    relative = path.relative_to(ROOT)
    lowered = tuple(part.lower() for part in relative.parts)
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return "private-material file extension"
    for parts in FORBIDDEN_PATH_PARTS:
        if lowered[: len(parts)] == parts:
            return "private-material directory"
    return None


def scan() -> list[str]:
    violations: list[str] = []
    boundaries = _private_boundaries()
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or _ignored(path):
            continue
        path_reason = _forbidden_path(path)
        if path_reason is not None:
            violations.append(f"{path.relative_to(ROOT)}: {path_reason}")
            continue
        if path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in boundaries:
            if pattern.search(text):
                violations.append(
                    f"{path.relative_to(ROOT)}: private key boundary detected"
                )
                break
        else:
            for pattern in SENSITIVE_ASSIGNMENTS:
                if pattern.search(text):
                    violations.append(
                        f"{path.relative_to(ROOT)}: credential-like assignment detected"
                    )
                    break
    return violations


def main() -> int:
    violations = scan()
    if violations:
        print("Repository secret check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("Repository secret check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
