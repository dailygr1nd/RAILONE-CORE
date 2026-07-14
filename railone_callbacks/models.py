from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class CallbackState(StrEnum):
    RECEIVED = "RECEIVED"
    APPLIED = "APPLIED"


@dataclass(frozen=True, slots=True)
class CallbackInboxRecord:
    provider_id: str
    provider_event_id: str
    payload_sha256: str
    normalized_payload: Mapping[str, object]
    signature_valid: bool
    state: CallbackState
    received_at: datetime
    applied_at: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "normalized_payload", MappingProxyType(dict(self.normalized_payload))
        )


@dataclass(frozen=True, slots=True)
class CallbackApplicationResult:
    provider_event_id: str
    rtt_id: str | None
    disposition: str
    duplicate: bool
