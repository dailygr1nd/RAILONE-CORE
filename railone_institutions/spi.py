"""Adapter protocol plus compatibility bridge into provider submission."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from railone_operations.models import (
    ProviderExecutionRequest,
    ProviderOutcome,
    ProviderSubmissionResult,
    RejectionDisposition,
)

from .models import (
    AdapterDescriptor,
    AdapterHealth,
    CanonicalInstitutionEvent,
    InstitutionCallback,
    InstitutionCapabilityManifest,
    InstitutionExecutionInstruction,
    InstitutionOutcome,
    InstitutionStatusResult,
    InstitutionSubmissionResult,
)


class InstitutionAdapter(Protocol):
    descriptor: AdapterDescriptor

    def capabilities(self) -> InstitutionCapabilityManifest: ...

    def validate_instruction(self, instruction: InstitutionExecutionInstruction) -> None: ...

    def submit(self, instruction: InstitutionExecutionInstruction) -> InstitutionSubmissionResult: ...

    def query_status(self, *, external_reference: str) -> InstitutionStatusResult: ...

    def reconcile(self, *, from_instant: datetime, to_instant: datetime) -> tuple[InstitutionStatusResult, ...]: ...

    def normalize_callback(self, callback: InstitutionCallback) -> CanonicalInstitutionEvent: ...

    def health(self) -> AdapterHealth: ...


class InstitutionAdapterBridge:
    """Preserves the stable coordinator contract while adapters adopt the richer SPI."""

    def __init__(self, adapter: InstitutionAdapter) -> None:
        self._adapter = adapter
        self.provider_id = adapter.descriptor.provider_id
        self.supports_idempotency = adapter.capabilities().supports_idempotency

    @property
    def binding_ref(self) -> str:
        return self._adapter.descriptor.binding_ref

    def submit(self, request: ProviderExecutionRequest) -> ProviderSubmissionResult:
        if request.adapter_binding_ref != self.binding_ref:
            raise ValueError("RTT adapter binding does not match dispatched adapter version")
        instruction = InstitutionExecutionInstruction.from_provider_request(request)
        self._adapter.validate_instruction(instruction)
        result = self._adapter.submit(instruction)
        if result.outcome is InstitutionOutcome.ACCEPTED_FOR_PROCESSING:
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.ACCEPTED,
                code=result.code,
                external_reference=result.external_reference,
                provider_context=(("adapter_binding_ref", self.binding_ref),),
            )
        if result.outcome is InstitutionOutcome.REJECTED_RETRYABLE:
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.REJECTED,
                code=result.code,
                external_reference=result.external_reference,
                rejection_disposition=RejectionDisposition.RETRYABLE,
                provider_context=(("adapter_binding_ref", self.binding_ref),),
            )
        if result.outcome is InstitutionOutcome.REJECTED_TERMINAL:
            return ProviderSubmissionResult(
                outcome=ProviderOutcome.REJECTED,
                code=result.code,
                external_reference=result.external_reference,
                rejection_disposition=RejectionDisposition.TERMINAL,
                provider_context=(("adapter_binding_ref", self.binding_ref),),
            )
        return ProviderSubmissionResult(
            outcome=ProviderOutcome.UNKNOWN,
            code=result.code,
            external_reference=result.external_reference,
            provider_context=(("adapter_binding_ref", self.binding_ref),),
        )
