from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EffectScenario(StrEnum):
    SUCCESS = "SUCCESS"
    REJECTED_RETRYABLE = "REJECTED_RETRYABLE"
    REJECTED_TERMINAL = "REJECTED_TERMINAL"
    UNKNOWN_AFTER_SEND = "UNKNOWN_AFTER_SEND"
    TIMEOUT_THEN_SUCCESS = "TIMEOUT_THEN_SUCCESS"


class EffectDeliveryState(StrEnum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    DELIVERED = "DELIVERED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True, slots=True)
class ScheduledProviderEffect:
    effect_id: str
    provider_id: str
    rtt_id: str
    external_reference: str
    effect_type: str
    provider_code: str
    due_tick: int
    payload: bytes


@dataclass(frozen=True, slots=True)
class ProviderEffectRecord:
    effect: ScheduledProviderEffect
    available_tick: int
    state: EffectDeliveryState = EffectDeliveryState.PENDING
    delivery_attempts: int = 0
    lease_owner: str | None = None
    lease_until_tick: int | None = None
    last_error: str | None = None
    delivered_at_tick: int | None = None
    version: int = 1
