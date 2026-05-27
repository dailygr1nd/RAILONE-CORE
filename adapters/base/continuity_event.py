from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContinuityEvent:

    railone_execution_id: str

    provider: str

    provider_reference: str

    canonical_state: str

    event_timestamp: datetime

    replay_safe_hash: str

    raw_payload: dict