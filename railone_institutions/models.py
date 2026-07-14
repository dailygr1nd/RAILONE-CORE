"""Canonical models crossing the RailOne/institution trust boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Any, Mapping

from railone_crypto.signature_service import SignatureEnvelope
from railone_operations.models import ProviderExecutionRequest


class AdapterEnvironment(StrEnum):
    SANDBOX = "SANDBOX"
    PILOT = "PILOT"
    PRODUCTION = "PRODUCTION"


class TransportKind(StrEnum):
    HTTPS = "HTTPS"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"
    SFTP = "SFTP"
    ISO_GATEWAY = "ISO_GATEWAY"


class MessageStandard(StrEnum):
    JSON = "JSON"
    ISO20022 = "ISO20022"
    PROPRIETARY = "PROPRIETARY"


class InstitutionAuthProfile(StrEnum):
    SIMULATION = "SIMULATION"
    MTLS = "MTLS"
    OAUTH2_MTLS = "OAUTH2_MTLS"
    OAUTH2_CLIENT_CREDENTIALS = "OAUTH2_CLIENT_CREDENTIALS"
    FAPI2_MTLS = "FAPI2_MTLS"
    DPOP = "DPOP"
    HMAC = "HMAC"


class InstitutionOperation(StrEnum):
    SUBMIT = "SUBMIT"
    STATUS_QUERY = "STATUS_QUERY"
    RECONCILE = "RECONCILE"
    CALLBACK = "CALLBACK"


class InstitutionOutcome(StrEnum):
    ACCEPTED_FOR_PROCESSING = "ACCEPTED_FOR_PROCESSING"
    REJECTED_RETRYABLE = "REJECTED_RETRYABLE"
    REJECTED_TERMINAL = "REJECTED_TERMINAL"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    PENDING = "PENDING"
    CONFIRMED_SUCCESS = "CONFIRMED_SUCCESS"
    CONFIRMED_FAILURE = "CONFIRMED_FAILURE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class FinalityLevel(IntEnum):
    NONE = 0
    PROCESSING = 1
    DEBIT_CONFIRMED = 2
    CREDIT_CONFIRMED = 3
    SETTLED = 4


class AdapterCertificationStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFORMANCE = "CONFORMANCE"
    CERTIFIED = "CERTIFIED"
    SUSPENDED = "SUSPENDED"


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


def _identifier(name: str, value: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is not a valid stable identifier")
    return value


def _codes(name: str, values: tuple[str, ...], *, width: int | None = None) -> tuple[str, ...]:
    normalized = tuple(sorted({str(value).upper() for value in values}))
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    if width is not None and any(len(value) != width or not value.isalpha() for value in normalized):
        raise ValueError(f"{name} must contain {width}-letter codes")
    return normalized


def _instant(name: str, value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    adapter_id: str
    adapter_version: str
    provider_id: str
    network_id: str
    environment: AdapterEnvironment
    transport: TransportKind
    message_standard: MessageStandard
    auth_profile: InstitutionAuthProfile
    certification_status: AdapterCertificationStatus
    priority: int = 100

    def __post_init__(self) -> None:
        for name in ("adapter_id", "provider_id", "network_id"):
            object.__setattr__(self, name, _identifier(name, getattr(self, name)))
        if not _SEMVER.fullmatch(self.adapter_version):
            raise ValueError("adapter_version must be semantic version syntax")
        if self.priority < 0:
            raise ValueError("priority cannot be negative")
        if self.environment is not AdapterEnvironment.SANDBOX and self.auth_profile is InstitutionAuthProfile.SIMULATION:
            raise ValueError("simulation authentication is sandbox-only")

    @property
    def binding_ref(self) -> str:
        return f"{self.adapter_id}@{self.adapter_version}"

    def to_payload(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "provider_id": self.provider_id,
            "network_id": self.network_id,
            "environment": self.environment.value,
            "transport": self.transport.value,
            "message_standard": self.message_standard.value,
            "auth_profile": self.auth_profile.value,
            "certification_status": self.certification_status.value,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class InstitutionCapabilityManifest:
    manifest_id: str
    manifest_version: int
    descriptor: AdapterDescriptor
    source_institution_ids: tuple[str, ...]
    destination_institution_ids: tuple[str, ...]
    source_countries: tuple[str, ...]
    destination_countries: tuple[str, ...]
    rails: tuple[str, ...]
    currencies_from: tuple[str, ...]
    currencies_to: tuple[str, ...]
    operations: tuple[InstitutionOperation, ...]
    supports_idempotency: bool
    supports_callbacks: bool
    supports_active_status: bool
    supports_reconciliation: bool
    asserted_finality: FinalityLevel
    min_amount_minor: int
    max_amount_minor: int
    request_timeout_seconds: int
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", _identifier("manifest_id", self.manifest_id))
        if self.manifest_version < 1:
            raise ValueError("manifest_version must be positive")
        object.__setattr__(self, "source_institution_ids", _codes("source_institution_ids", self.source_institution_ids))
        object.__setattr__(self, "destination_institution_ids", _codes("destination_institution_ids", self.destination_institution_ids))
        object.__setattr__(self, "source_countries", _codes("source_countries", self.source_countries, width=2))
        object.__setattr__(self, "destination_countries", _codes("destination_countries", self.destination_countries, width=2))
        object.__setattr__(self, "rails", _codes("rails", self.rails))
        object.__setattr__(self, "currencies_from", _codes("currencies_from", self.currencies_from, width=3))
        object.__setattr__(self, "currencies_to", _codes("currencies_to", self.currencies_to, width=3))
        object.__setattr__(self, "operations", tuple(sorted(set(self.operations), key=lambda item: item.value)))
        if InstitutionOperation.SUBMIT not in self.operations:
            raise ValueError("adapter capabilities must include SUBMIT")
        if self.min_amount_minor < 1 or self.max_amount_minor < self.min_amount_minor:
            raise ValueError("invalid amount range")
        if not 1 <= self.request_timeout_seconds <= 300:
            raise ValueError("request timeout must be between 1 and 300 seconds")
        issued = _instant("issued_at", self.issued_at)
        expires = _instant("expires_at", self.expires_at)
        if expires <= issued:
            raise ValueError("expires_at must be after issued_at")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "expires_at", expires)
        if self.supports_callbacks != (InstitutionOperation.CALLBACK in self.operations):
            raise ValueError("callback flag must agree with operations")
        if self.supports_active_status != (InstitutionOperation.STATUS_QUERY in self.operations):
            raise ValueError("status flag must agree with operations")
        if self.supports_reconciliation != (InstitutionOperation.RECONCILE in self.operations):
            raise ValueError("reconciliation flag must agree with operations")
        if self.asserted_finality is FinalityLevel.SETTLED and not (
            self.supports_callbacks or self.supports_active_status or self.supports_reconciliation
        ):
            raise ValueError("settlement finality requires an evidence retrieval operation")

    def is_active_at(self, instant: datetime) -> bool:
        value = _instant("instant", instant)
        return self.issued_at <= value < self.expires_at and self.descriptor.certification_status is not AdapterCertificationStatus.SUSPENDED

    def to_payload(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "manifest_version": self.manifest_version,
            "descriptor": self.descriptor.to_payload(),
            "source_institution_ids": list(self.source_institution_ids),
            "destination_institution_ids": list(self.destination_institution_ids),
            "source_countries": list(self.source_countries),
            "destination_countries": list(self.destination_countries),
            "rails": list(self.rails),
            "currencies_from": list(self.currencies_from),
            "currencies_to": list(self.currencies_to),
            "operations": [item.value for item in self.operations],
            "supports_idempotency": self.supports_idempotency,
            "supports_callbacks": self.supports_callbacks,
            "supports_active_status": self.supports_active_status,
            "supports_reconciliation": self.supports_reconciliation,
            "asserted_finality": self.asserted_finality.name,
            "min_amount_minor": self.min_amount_minor,
            "max_amount_minor": self.max_amount_minor,
            "request_timeout_seconds": self.request_timeout_seconds,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SignedCapabilityManifest:
    manifest: InstitutionCapabilityManifest
    signature: SignatureEnvelope


@dataclass(frozen=True, slots=True)
class InstitutionExecutionInstruction:
    idempotency_key: str
    request_sha256: str
    utt_id: str
    rtt_id: str
    attempt_number: int
    provider_id: str
    adapter_binding_ref: str
    rail: str
    amount_minor: int
    currency_from: str
    receive_amount_minor: int
    currency_to: str
    source_institution_id: str
    destination_institution_id: str
    payer_account_reference: str = field(repr=False)
    beneficiary_account_reference: str = field(repr=False)

    def __post_init__(self) -> None:
        required = (
            "idempotency_key", "utt_id", "rtt_id", "provider_id",
            "adapter_binding_ref", "rail",
            "source_institution_id", "destination_institution_id",
            "payer_account_reference", "beneficiary_account_reference",
        )
        for name in required:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"{name} must be a non-empty bounded string")
        if not re.fullmatch(r"[a-f0-9]{64}", self.request_sha256):
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        if "@" not in self.adapter_binding_ref:
            raise ValueError("adapter_binding_ref must pin adapter_id@version")
        if isinstance(self.attempt_number, bool) or self.attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        for name in ("amount_minor", "receive_amount_minor"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("currency_from", "currency_to"):
            value = getattr(self, name)
            if not re.fullmatch(r"[A-Z]{3}", value):
                raise ValueError(f"{name} must be an uppercase ISO-style currency code")

    @classmethod
    def from_provider_request(cls, request: ProviderExecutionRequest) -> "InstitutionExecutionInstruction":
        return cls(**{name: getattr(request, name) for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class InstitutionSubmissionResult:
    outcome: InstitutionOutcome
    code: str
    external_reference: str | None = None
    finality: FinalityLevel = FinalityLevel.NONE
    evidence: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.outcome is InstitutionOutcome.ACCEPTED_FOR_PROCESSING and self.finality > FinalityLevel.PROCESSING:
            raise ValueError("provider acceptance cannot assert credit or settlement finality")
        if self.outcome is InstitutionOutcome.CONFIRMED_SUCCESS and self.finality < FinalityLevel.CREDIT_CONFIRMED:
            raise ValueError("confirmed success requires credit-confirmed or settled finality")


@dataclass(frozen=True, slots=True)
class InstitutionStatusResult:
    outcome: InstitutionOutcome
    code: str
    external_reference: str
    finality: FinalityLevel
    observed_at: datetime
    evidence: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _instant("observed_at", self.observed_at))


@dataclass(frozen=True, slots=True)
class InstitutionCallback:
    provider_id: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)
    received_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "received_at", _instant("received_at", self.received_at))
        if len(self.body) > 1_000_000:
            raise ValueError("callback body exceeds the canonical ingress limit")


@dataclass(frozen=True, slots=True)
class CanonicalInstitutionEvent:
    event_id: str
    adapter_binding_ref: str
    provider_id: str
    external_reference: str
    outcome: InstitutionOutcome
    finality: FinalityLevel
    observed_at: datetime
    evidence_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _instant("observed_at", self.observed_at))
        if not re.fullmatch(r"[a-f0-9]{64}", self.evidence_sha256):
            raise ValueError("evidence_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    available: bool
    checked_at: datetime
    latency_ms: int | None = None
    reason_code: str = "OK"

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", _instant("checked_at", self.checked_at))
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
