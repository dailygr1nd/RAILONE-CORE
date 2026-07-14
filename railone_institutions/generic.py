"""Configured HTTP institution adapter with explicit outcome normalization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol
from urllib.parse import quote

from railone_crypto.canonical_json import canonical_json_bytes

from .auth import InstitutionAuthStrategy
from .codecs import InstitutionMessageCodec, decode_json_object
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
from .transport import InstitutionHttpRequest, InstitutionTransport, InstitutionTransportError


@dataclass(frozen=True, slots=True)
class GenericHttpAdapterConfig:
    submit_url: str
    status_url_template: str
    timeout_seconds: int
    outcome_field: str = "status"
    external_reference_field: str = "reference"


class InstitutionCallbackVerifier(Protocol):
    def verify(self, callback: InstitutionCallback) -> None: ...


class InstitutionReconciliationProvider(Protocol):
    def reconcile(self, *, from_instant: datetime, to_instant: datetime) -> tuple[InstitutionStatusResult, ...]: ...


class ExplicitOutcomeNormalizer:
    """Only configured codes have meaning; an unmapped code is never guessed."""

    def __init__(
        self,
        *,
        submission_codes: Mapping[str, InstitutionOutcome],
        status_codes: Mapping[str, tuple[InstitutionOutcome, FinalityLevel]],
    ) -> None:
        self._submission = {str(key).upper(): value for key, value in submission_codes.items()}
        self._status = {str(key).upper(): value for key, value in status_codes.items()}

    def submission(self, code: str) -> InstitutionOutcome:
        return self._submission.get(code.upper(), InstitutionOutcome.OUTCOME_UNKNOWN)

    def status(self, code: str) -> tuple[InstitutionOutcome, FinalityLevel]:
        return self._status.get(code.upper(), (InstitutionOutcome.RECONCILIATION_REQUIRED, FinalityLevel.NONE))


class GenericHttpInstitutionAdapter:
    def __init__(
        self,
        *,
        descriptor: AdapterDescriptor,
        manifest: InstitutionCapabilityManifest,
        config: GenericHttpAdapterConfig,
        codec: InstitutionMessageCodec,
        auth: InstitutionAuthStrategy,
        transport: InstitutionTransport,
        normalizer: ExplicitOutcomeNormalizer,
        callback_verifier: InstitutionCallbackVerifier | None = None,
        reconciliation_provider: InstitutionReconciliationProvider | None = None,
    ) -> None:
        if descriptor != manifest.descriptor:
            raise ValueError("adapter descriptor and manifest must match")
        self.descriptor = descriptor
        self._manifest = manifest
        self._config = config
        self._codec = codec
        self._auth = auth
        self._transport = transport
        self._normalizer = normalizer
        self._callback_verifier = callback_verifier
        self._reconciliation_provider = reconciliation_provider
        if manifest.supports_callbacks and callback_verifier is None:
            raise ValueError("callback-capable adapters require an ingress authenticator")
        if manifest.supports_reconciliation and reconciliation_provider is None:
            raise ValueError("reconciliation-capable adapters require a reconciliation provider")

    def capabilities(self) -> InstitutionCapabilityManifest:
        return self._manifest

    def validate_instruction(self, instruction: InstitutionExecutionInstruction) -> None:
        manifest = self._manifest
        if instruction.provider_id.upper() != self.descriptor.provider_id.upper():
            raise ValueError("instruction provider does not match adapter")
        checks = (
            (instruction.source_institution_id.upper(), manifest.source_institution_ids, "source institution"),
            (instruction.destination_institution_id.upper(), manifest.destination_institution_ids, "destination institution"),
            (instruction.rail.upper(), manifest.rails, "rail"),
            (instruction.currency_from.upper(), manifest.currencies_from, "source currency"),
            (instruction.currency_to.upper(), manifest.currencies_to, "destination currency"),
        )
        for value, supported, label in checks:
            if value not in supported:
                raise ValueError(f"unsupported {label}")
        if not manifest.min_amount_minor <= instruction.amount_minor <= manifest.max_amount_minor:
            raise ValueError("amount is outside adapter capability range")

    def submit(self, instruction: InstitutionExecutionInstruction) -> InstitutionSubmissionResult:
        self.validate_instruction(instruction)
        request = InstitutionHttpRequest(
            method="POST",
            url=self._config.submit_url,
            headers={
                "Content-Type": self._codec.content_type,
                "Accept": "application/json",
                "Idempotency-Key": instruction.idempotency_key,
                "X-RailOne-RTT": instruction.rtt_id,
            },
            body=self._codec.encode_submission(instruction),
            timeout_seconds=self._config.timeout_seconds,
        )
        try:
            response = self._transport.send(self._auth.authenticate(request))
        except InstitutionTransportError:
            return InstitutionSubmissionResult(
                InstitutionOutcome.OUTCOME_UNKNOWN, "TRANSPORT_OUTCOME_UNKNOWN"
            )
        try:
            payload = decode_json_object(response.body)
            code = str(payload[self._config.outcome_field]).upper()
            reference_value = payload.get(self._config.external_reference_field)
            reference = str(reference_value) if reference_value is not None else None
        except (ValueError, KeyError, UnicodeError):
            return InstitutionSubmissionResult(
                InstitutionOutcome.OUTCOME_UNKNOWN, "UNPARSEABLE_PROVIDER_RESPONSE"
            )
        outcome = self._normalizer.submission(code)
        return InstitutionSubmissionResult(
            outcome=outcome,
            code=code,
            external_reference=reference,
            finality=FinalityLevel.PROCESSING if outcome is InstitutionOutcome.ACCEPTED_FOR_PROCESSING else FinalityLevel.NONE,
        )

    def query_status(self, *, external_reference: str) -> InstitutionStatusResult:
        if not self._manifest.supports_active_status:
            raise PermissionError("active status is not enabled for this adapter")
        url = self._config.status_url_template.format(reference=quote(external_reference, safe=""))
        request = InstitutionHttpRequest(
            method="GET", url=url, headers={"Accept": "application/json"}, timeout_seconds=self._config.timeout_seconds
        )
        try:
            response = self._transport.send(self._auth.authenticate(request))
            payload = decode_json_object(response.body)
            code = str(payload[self._config.outcome_field]).upper()
            outcome, finality = self._normalizer.status(code)
        except InstitutionTransportError:
            code, outcome, finality = "STATUS_TRANSPORT_UNKNOWN", InstitutionOutcome.RECONCILIATION_REQUIRED, FinalityLevel.NONE
        except (ValueError, KeyError, UnicodeError):
            code, outcome, finality = "UNPARSEABLE_STATUS_RESPONSE", InstitutionOutcome.RECONCILIATION_REQUIRED, FinalityLevel.NONE
        return InstitutionStatusResult(outcome, code, external_reference, finality, datetime.now(timezone.utc))

    def reconcile(self, *, from_instant: datetime, to_instant: datetime) -> tuple[InstitutionStatusResult, ...]:
        if self._reconciliation_provider is None:
            raise PermissionError("reconciliation is not enabled for this adapter")
        return self._reconciliation_provider.reconcile(
            from_instant=from_instant, to_instant=to_instant
        )

    def normalize_callback(self, callback: InstitutionCallback) -> CanonicalInstitutionEvent:
        if self._callback_verifier is None:
            raise PermissionError("callbacks are not enabled for this adapter")
        self._callback_verifier.verify(callback)
        payload = decode_json_object(callback.body)
        code = str(payload[self._config.outcome_field]).upper()
        reference = str(payload[self._config.external_reference_field])
        outcome, finality = self._normalizer.status(code)
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        return CanonicalInstitutionEvent(
            event_id=f"IAE-{digest[:32].upper()}",
            adapter_binding_ref=self.descriptor.binding_ref,
            provider_id=self.descriptor.provider_id,
            external_reference=reference,
            outcome=outcome,
            finality=finality,
            observed_at=callback.received_at,
            evidence_sha256=digest,
        )

    def health(self) -> AdapterHealth:
        return AdapterHealth(True, datetime.now(timezone.utc), reason_code="CONFIGURED")
