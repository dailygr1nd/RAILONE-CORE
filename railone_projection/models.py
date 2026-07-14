"""Exactly-once read model for provider execution progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ProviderProgressState(StrEnum):
    PREPARED = "PREPARED"
    DISPATCHING = "DISPATCHING"
    ACCEPTED_FOR_PROCESSING = "ACCEPTED_FOR_PROCESSING"
    REJECTED = "REJECTED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderOutcomeProjection:
    submission_id: str
    utt_id: str
    rtt_id: str
    provider_id: str
    state: ProviderProgressState
    normalized_code: str | None
    external_reference: str | None
    rejection_disposition: str | None
    submission_version: int
    source_event_id: str
    occurred_at: datetime
    projected_at: datetime
