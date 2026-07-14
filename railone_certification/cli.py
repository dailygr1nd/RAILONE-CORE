"""Offline certification trace evaluator for partner CI pipelines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .codec import load_trace_json
from .models import CertificationStatus
from .reference import SyntheticReferenceCertificationDriver
from .runner import CertificationRunner, CertificationSuite


class DirectoryTraceDriver:
    def __init__(self, directory: Path, adapter_binding_ref: str) -> None:
        self._directory = directory
        self.adapter_binding_ref = adapter_binding_ref

    def execute_case(self, *, run_id, scenario):
        path = self._directory / f"{scenario.value}.json"
        trace = load_trace_json(path.read_bytes())
        if trace.run_id != run_id:
            raise ValueError("trace run_id differs from requested certification run")
        return trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="railone-certify")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--adapter-binding", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--trace-directory", type=Path)
    source.add_argument("--synthetic-self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.synthetic_self_test:
        driver = SyntheticReferenceCertificationDriver(args.adapter_binding)
    else:
        if not args.trace_directory.is_dir():
            parser.error("--trace-directory must identify a directory")
        driver = DirectoryTraceDriver(args.trace_directory, args.adapter_binding)
    report = CertificationRunner().run(
        run_id=args.run_id, driver=driver,
        manifest_payload_sha256=args.manifest_sha256,
        suite=CertificationSuite.pilot_v1(),
    )
    # Offline evaluation is deliberately unsigned. Only the isolated signer-backed
    # CertificationReportService can create authoritative certification evidence.
    output = {
        "classification": "UNSIGNED_CERTIFICATION_DRAFT",
        "authoritative": False,
        "report": report.to_payload(),
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if report.status is CertificationStatus.PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
