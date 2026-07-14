"""Provider-independent conformance checks reusable by future partner adapters."""

from __future__ import annotations

from .models import FinalityLevel, InstitutionExecutionInstruction, InstitutionOutcome
from .spi import InstitutionAdapter


def assert_adapter_submission_conformance(
    adapter: InstitutionAdapter,
    instruction: InstitutionExecutionInstruction,
) -> None:
    manifest = adapter.capabilities()
    if adapter.descriptor != manifest.descriptor:
        raise AssertionError("descriptor must equal the signed capability descriptor")
    adapter.validate_instruction(instruction)
    first = adapter.submit(instruction)
    if first.outcome is InstitutionOutcome.ACCEPTED_FOR_PROCESSING and first.finality > FinalityLevel.PROCESSING:
        raise AssertionError("submission acceptance cannot claim final settlement")
    if manifest.supports_idempotency:
        second = adapter.submit(instruction)
        if (second.outcome, second.code, second.external_reference) != (
            first.outcome, first.code, first.external_reference
        ):
            raise AssertionError("idempotent replay changed provider outcome")
