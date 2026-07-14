"""Run the cumulative RailOne pilot baseline tests from any working directory."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
TESTS_ROOT = PROJECT_ROOT / "tests"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TESTS_ROOT),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
