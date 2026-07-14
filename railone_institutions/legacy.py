"""Migration plug-in for provider adapters that already implement safe submission."""

from __future__ import annotations

from datetime import datetime, timezone

from railone_operations.models import (
    ProviderExecutionRequest,
    ProviderOutcome,
    RejectionDisposition,
)
from railone_operations.service import ProviderAdapter

from .models import (
    AdapterDescriptor,
    AdapterHealth,
    CanonicalInstitutionEvent,
    FinalityLevel,
    InstitutionCallback,
    InstitutionCapabilityManifest,
    InstitutionExecutionInstruction,
    InstitutionOutcome,
    InstitutionStatusResult,
    InstitutionSubmissionResult,
)


class ProviderAdapterInstitutionPlugin:
    """Moves a vetted submit-only adapter behind the Step 11D SPI."""

    def __init__(
        self,
        *,
        adapter: ProviderAdapter,
        descriptor: AdapterDescriptor,
        manifest: InstitutionCapabilityManifest,
    ) -> None:
        if descriptor != manifest.descriptor:
            raise ValueError("adapter descriptor and manifest must match")
        if adapter.provider_id.upper() != descriptor.provider_id.upper():
            raise ValueError("legacy provider id does not match adapter descriptor")
        if adapter.supports_idempotency != manifest.supports_idempotency:
            raise ValueError("legacy idempotency behavior differs from manifest")
        if manifest.supports_callbacks or manifest.supports_active_status or manifest.supports_reconciliation:
            raise ValueError("submit-only migration plug-in cannot advertise evidence operations")
        self.descriptor = descriptor
        self._manifest = manifest
        self._adapter = adapter

    def capabilities(self) -> InstitutionCapabilityManifest:
        return self._manifest

    def validate_instruction(self, instruction: InstitutionExecutionInstruction) -> None:
        if instruction.adapter_binding_ref != self.descriptor.binding_ref:
            raise ValueError("RTT adapter binding does not match plug-in")
        if instruction.provider_id.upper() != self.descriptor.provider_id.upper():
            raise ValueError("provider mismatch")
        if instruction.rail.upper() not in self._manifest.rails:
            raise ValueError("unsupported rail")
        if instruction.source_institution_id.upper() not in self._manifest.source_institution_ids:
            raise ValueError("unsupported source institution")
        if instruction.destination_institution_id.upper() not in self._manifest.destination_institution_ids:
            raise ValueError("unsupported destination institution")

    def submit(self, instruction: InstitutionExecutionInstruction) -> InstitutionSubmissionResult:
        self.validate_instruction(instruction)
        request = ProviderExecutionRequest(**{
            name: getattr(instruction, name) for name in ProviderExecutionRequest.__dataclass_fields__
        })
        result = self._adapter.submit(request)
        if result.outcome is ProviderOutcome.ACCEPTED:
            outcome = InstitutionOutcome.ACCEPTED_FOR_PROCESSING
        elif result.outcome is ProviderOutcome.REJECTED:
            outcome = (
                InstitutionOutcome.REJECTED_RETRYABLE
                if result.rejection_disposition is RejectionDisposition.RETRYABLE
                else InstitutionOutcome.REJECTED_TERMINAL
            )
        else:
            outcome = InstitutionOutcome.OUTCOME_UNKNOWN
        return InstitutionSubmissionResult(
            outcome, result.code, result.external_reference,
            FinalityLevel.PROCESSING if outcome is InstitutionOutcome.ACCEPTED_FOR_PROCESSING else FinalityLevel.NONE,
        )

    def query_status(self, *, external_reference: str) -> InstitutionStatusResult:
        raise NotImplementedError("provider-specific status plug-in is not configured")

    def reconcile(self, *, from_instant: datetime, to_instant: datetime) -> tuple[InstitutionStatusResult, ...]:
        raise NotImplementedError("provider-specific reconciliation plug-in is not configured")

    def normalize_callback(self, callback: InstitutionCallback) -> CanonicalInstitutionEvent:
        raise PermissionError("callbacks remain on the provider-specific authenticated processor")

    def health(self) -> AdapterHealth:
        return AdapterHealth(True, datetime.now(timezone.utc), reason_code="LEGACY_SUBMIT_PLUGIN")
