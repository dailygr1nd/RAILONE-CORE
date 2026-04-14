# ==============================
# state_machine.py
# ==============================
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any


class TransactionState(str, Enum):
    INIT = "INIT"
    SENDER_LOCKED = "SENDER_LOCKED"
    ROUTING = "ROUTING"
    RECEIVER_CONFIRMED = "RECEIVER_CONFIRMED"
    HANDSHAKE_VERIFIED = "HANDSHAKE_VERIFIED"
    PROCESSED = "PROCESSED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


VALID_TRANSITIONS = {
    TransactionState.INIT: [TransactionState.SENDER_LOCKED, TransactionState.FAILED],
    TransactionState.SENDER_LOCKED: [TransactionState.ROUTING, TransactionState.ROLLED_BACK],
    TransactionState.ROUTING: [TransactionState.RECEIVER_CONFIRMED, TransactionState.FAILED],
    TransactionState.RECEIVER_CONFIRMED: [TransactionState.HANDSHAKE_VERIFIED, TransactionState.FAILED],
    TransactionState.HANDSHAKE_VERIFIED: [TransactionState.PROCESSED, TransactionState.FAILED],
    TransactionState.PROCESSED: [TransactionState.SETTLED, TransactionState.ROLLED_BACK],
    TransactionState.SETTLED: [],
    TransactionState.FAILED: [TransactionState.ROLLED_BACK],
    TransactionState.ROLLED_BACK: [],
}


@dataclass
class TransactionContext:
    utt: str
    amount: float
    currency: str
    sender_id: str
    receiver_id: str
    state: TransactionState = TransactionState.INIT
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition(self, new_state: TransactionState):
        allowed = VALID_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(f"Invalid transition: {self.state} -> {new_state}")

        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self

    def to_dict(self):
        return {
            "utt": self.utt,
            "amount": self.amount,
            "currency": self.currency,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "state": self.state.value,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
