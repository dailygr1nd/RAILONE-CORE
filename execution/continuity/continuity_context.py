from dataclasses import dataclass
from typing import Optional


@dataclass
class ContinuityContext:

    continuity_uid: str

    utt_id: str

    rtt_id: Optional[str]

    sender_id: str

    receiver_id: str

    amount: float

    currency: str

    replay_generation: int = 0