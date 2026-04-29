# ==============================
# state_machine.py (FIXED + COMPLETE)
# ==============================

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any


# --------------------------------
# STATES
# --------------------------------
class TransactionState(str, Enum):

    # INIT
    INIT = "INIT"

    # IDENTITY + HANDSHAKE
    IDENTITY_VERIFIED = "IDENTITY_VERIFIED"
    INTENT_LOCKED = "INTENT_LOCKED"      # ETK-S
    RECEIVER_CONFIRMED = "RECEIVER_CONFIRMED"  # ETK-R
    HANDSHAKE_VERIFIED = "HANDSHAKE_VERIFIED"  # RTT

    # DECISION
    ROUTE_COMPUTED = "ROUTE_COMPUTED"
    PRICED = "PRICED"
    VALIDATED = "VALIDATED"

    # EXECUTION PIPELINE
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_CONFIRMED = "EXECUTION_CONFIRMED"
    EXECUTION_FAILED = "EXECUTION_FAILED"

    # FINALITY
    SETTLED = "SETTLED"
    FINALIZED = "FINALIZED"

    # FAILURE
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


# --------------------------------
# VALID TRANSITIONS
# --------------------------------
VALID_TRANSITIONS = {

    TransactionState.INIT: [
        TransactionState.IDENTITY_VERIFIED,
        TransactionState.FAILED
    ],

    TransactionState.IDENTITY_VERIFIED: [
        TransactionState.INTENT_LOCKED,
        TransactionState.FAILED
    ],

    TransactionState.INTENT_LOCKED: [
        TransactionState.RECEIVER_CONFIRMED,
        TransactionState.FAILED
    ],

    TransactionState.RECEIVER_CONFIRMED: [
        TransactionState.HANDSHAKE_VERIFIED,
        TransactionState.FAILED
    ],

    TransactionState.HANDSHAKE_VERIFIED: [
        TransactionState.ROUTE_COMPUTED,
        TransactionState.FAILED
    ],

    TransactionState.ROUTE_COMPUTED: [
        TransactionState.PRICED,
        TransactionState.FAILED
    ],

    TransactionState.PRICED: [
        TransactionState.VALIDATED,
        TransactionState.FAILED
    ],

    TransactionState.VALIDATED: [
        TransactionState.DISPATCHED,
        TransactionState.FAILED
    ],

    TransactionState.DISPATCHED: [
        TransactionState.EXECUTION_STARTED,
        TransactionState.FAILED
    ],

    TransactionState.EXECUTION_STARTED: [
        TransactionState.EXECUTION_CONFIRMED,
        TransactionState.EXECUTION_FAILED
    ],

    TransactionState.EXECUTION_FAILED: [
        TransactionState.ROLLED_BACK,
        TransactionState.FAILED
    ],

    TransactionState.EXECUTION_CONFIRMED: [
        TransactionState.SETTLED
    ],

    TransactionState.SETTLED: [
        TransactionState.FINALIZED
    ],

    TransactionState.FINALIZED: [],

    TransactionState.FAILED: [
        TransactionState.ROLLED_BACK
    ],

    TransactionState.ROLLED_BACK: []
}


# --------------------------------
# CONTEXT OBJECT
# --------------------------------
@dataclass
class TransactionContext:
    tx_id: str
    amount: float
    currency: str
    sender_id: str
    receiver_id: str

    state: TransactionState = TransactionState.INIT
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    metadata: Dict[str, Any] = field(default_factory=dict)

    # --------------------------------
    def transition(self, new_state: TransactionState):

        allowed = VALID_TRANSITIONS.get(self.state, [])

        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state} -> {new_state}"
            )

        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()

        return self

    # --------------------------------
    def attach(self, key: str, value: Any):
        self.metadata[key] = value
        return self

    # --------------------------------
    def to_dict(self):
        return {
            "tx_id": self.tx_id,
            "amount": self.amount,
            "currency": self.currency,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "state": self.state.value,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }