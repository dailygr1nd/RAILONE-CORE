"""Provider-submission and signed-outbox operational models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from railone_crypto.signature_service import SignatureEnvelope


class ProviderSubmissionState(StrEnum):
    PREPARED = "PREPARED"
    DISPATCHING = "DISPATCHING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ProviderOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class RejectionDisposition(StrEnum):
    RETRYABLE = "RETRYABLE"
    TERMINAL = "TERMINAL"


class OutboxDeliveryState(StrEnum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    PUBLISHED = "PUBLISHED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True, slots=True)
class ProviderExecutionRequest:
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


@dataclass(frozen=True, slots=True)
class ProviderSubmissionResult:
    outcome: ProviderOutcome
    code: str
    external_reference: str | None = None
    rejection_disposition: RejectionDisposition | None = None
    provider_context: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderSubmissionRecord:
    submission_id: str
    idempotency_key: str
    request_sha256: str
    utt_id: str
    rtt_id: str
    provider_id: str
    state: ProviderSubmissionState
    dispatch_attempts: int
    normalized_code: str | None
    external_reference: str | None
    rejection_disposition: RejectionDisposition | None
    provider_context: tuple[tuple[str, str], ...]
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    signed_event: SignatureEnvelope
    delivery_state: OutboxDeliveryState
    delivery_attempts: int
    available_at: datetime
    lease_owner: str | None
    lease_until: datetime | None
    last_error: str | None
    published_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
