"""Reference profiles for pilot adapters; these are not partner certifications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from railone_crypto.canonical_json import canonical_json_bytes

from .models import (
    AdapterCertificationStatus,
    AdapterDescriptor,
    AdapterEnvironment,
    AdapterHealth,
    CanonicalInstitutionEvent,
    FinalityLevel,
    InstitutionAuthProfile,
    InstitutionCallback,
    InstitutionCapabilityManifest,
    InstitutionExecutionInstruction,
    InstitutionOperation,
    InstitutionOutcome,
    InstitutionStatusResult,
    InstitutionSubmissionResult,
    MessageStandard,
    TransportKind,
)


@dataclass(frozen=True, slots=True)
class ReferenceProfile:
    adapter_id: str
    provider_id: str
    network_id: str
    rails: tuple[str, ...]
    currencies_from: tuple[str, ...]
    currencies_to: tuple[str, ...]
    source_countries: tuple[str, ...]
    destination_countries: tuple[str, ...]
    message_standard: MessageStandard


DOMESTIC_BANK_PROFILE = ReferenceProfile(
    "railone.reference.domestic-bank", "BANK-REFERENCE", "DOMESTIC-BANK-REFERENCE",
    ("DOMESTIC_BANK", "RTGS"), ("KES",), ("KES",), ("KE",), ("KE",), MessageStandard.ISO20022,
)
DOMESTIC_SWITCH_PROFILE = ReferenceProfile(
    "railone.reference.domestic-switch", "SWITCH-REFERENCE", "INSTANT-SWITCH-REFERENCE",
    ("INSTANT_ACCOUNT_TRANSFER",), ("KES",), ("KES",), ("KE",), ("KE",), MessageStandard.ISO20022,
)
CROSS_BORDER_PROFILE = ReferenceProfile(
    "railone.reference.cross-border", "CROSSBORDER-REFERENCE", "CROSS-BORDER-REFERENCE",
    ("CROSS_BORDER", "MOBILE_MONEY"), ("USD", "EGP", "KES"), ("KES", "TZS"),
    ("EG", "KE"), ("KE", "TZ"), MessageStandard.JSON,
)


def reference_manifest(
    profile: ReferenceProfile,
    *,
    source_institution_ids: tuple[str, ...],
    destination_institution_ids: tuple[str, ...],
    now: datetime | None = None,
) -> InstitutionCapabilityManifest:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    descriptor = AdapterDescriptor(
        adapter_id=profile.adapter_id,
        adapter_version="1.0.0",
        provider_id=profile.provider_id,
        network_id=profile.network_id,
        environment=AdapterEnvironment.SANDBOX,
        transport=TransportKind.HTTPS,
        message_standard=profile.message_standard,
        auth_profile=InstitutionAuthProfile.SIMULATION,
        certification_status=AdapterCertificationStatus.CONFORMANCE,
    )
    return InstitutionCapabilityManifest(
        manifest_id=f"manifest.{profile.adapter_id}",
        manifest_version=1,
        descriptor=descriptor,
        source_institution_ids=source_institution_ids,
        destination_institution_ids=destination_institution_ids,
        source_countries=profile.source_countries,
        destination_countries=profile.destination_countries,
        rails=profile.rails,
        currencies_from=profile.currencies_from,
        currencies_to=profile.currencies_to,
        operations=(InstitutionOperation.SUBMIT, InstitutionOperation.STATUS_QUERY, InstitutionOperation.RECONCILE),
        supports_idempotency=True,
        supports_callbacks=False,
        supports_active_status=True,
        supports_reconciliation=True,
        asserted_finality=FinalityLevel.SETTLED,
        min_amount_minor=1,
        max_amount_minor=100_000_000_00,
        request_timeout_seconds=20,
        issued_at=instant,
        expires_at=instant + timedelta(days=30),
    )


class ReferenceInstitutionAdapter:
    """Deterministic synthetic adapter for conformance and end-to-end pilot effects."""

    def __init__(self, manifest: InstitutionCapabilityManifest) -> None:
        if manifest.descriptor.environment is not AdapterEnvironment.SANDBOX:
            raise ValueError("reference adapter is sandbox-only")
        self.descriptor = manifest.descriptor
        self._manifest = manifest
        self._by_idempotency: dict[str, tuple[str, str]] = {}
        self._status: dict[str, InstitutionStatusResult] = {}

    def capabilities(self) -> InstitutionCapabilityManifest:
        return self._manifest

    def validate_instruction(self, instruction: InstitutionExecutionInstruction) -> None:
        if instruction.provider_id != self.descriptor.provider_id:
            raise ValueError("provider mismatch")
        if instruction.rail.upper() not in self._manifest.rails:
            raise ValueError("unsupported rail")
        if instruction.source_institution_id.upper() not in self._manifest.source_institution_ids:
            raise ValueError("unsupported source institution")
        if instruction.destination_institution_id.upper() not in self._manifest.destination_institution_ids:
            raise ValueError("unsupported destination institution")

    def submit(self, instruction: InstitutionExecutionInstruction) -> InstitutionSubmissionResult:
        self.validate_instruction(instruction)
        material_hash = hashlib.sha256(canonical_json_bytes({
            "request_sha256": instruction.request_sha256,
            "rtt_id": instruction.rtt_id,
        })).hexdigest()
        existing = self._by_idempotency.get(instruction.idempotency_key)
        if existing is not None:
            reference, prior_hash = existing
            if prior_hash != material_hash:
                return InstitutionSubmissionResult(InstitutionOutcome.REJECTED_TERMINAL, "IDEMPOTENCY_CONFLICT")
            return InstitutionSubmissionResult(InstitutionOutcome.ACCEPTED_FOR_PROCESSING, "ACCEPTED", reference, FinalityLevel.PROCESSING)
        reference = f"REF-{material_hash[:24].upper()}"
        self._by_idempotency[instruction.idempotency_key] = (reference, material_hash)
        self._status[reference] = InstitutionStatusResult(
            InstitutionOutcome.PENDING, "PENDING", reference, FinalityLevel.PROCESSING, datetime.now(timezone.utc)
        )
        return InstitutionSubmissionResult(InstitutionOutcome.ACCEPTED_FOR_PROCESSING, "ACCEPTED", reference, FinalityLevel.PROCESSING)

    def confirm_settlement(self, external_reference: str, *, at: datetime | None = None) -> None:
        if external_reference not in self._status:
            raise KeyError("unknown synthetic external reference")
        self._status[external_reference] = InstitutionStatusResult(
            InstitutionOutcome.CONFIRMED_SUCCESS, "SETTLED", external_reference,
            FinalityLevel.SETTLED, at or datetime.now(timezone.utc),
            evidence={"synthetic": True, "profile": self.descriptor.network_id},
        )

    def query_status(self, *, external_reference: str) -> InstitutionStatusResult:
        return self._status[external_reference]

    def reconcile(self, *, from_instant: datetime, to_instant: datetime) -> tuple[InstitutionStatusResult, ...]:
        return tuple(item for item in self._status.values() if from_instant <= item.observed_at <= to_instant)

    def normalize_callback(self, callback: InstitutionCallback) -> CanonicalInstitutionEvent:
        raise PermissionError("reference profile does not advertise callbacks")

    def health(self) -> AdapterHealth:
        return AdapterHealth(True, datetime.now(timezone.utc), reason_code="SYNTHETIC_REFERENCE")
