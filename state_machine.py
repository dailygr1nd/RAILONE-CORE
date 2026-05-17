# ==============================
# state_machine.py
# RailOne Deterministic Execution
# Continuity State Machine
# ==============================

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from event_emitter import emit_event


# ==========================================
# STATES
# ==========================================
class TransactionState(str, Enum):

    # --------------------------------
    # SESSION INITIALIZATION
    # --------------------------------
    INIT = "INIT"

    # --------------------------------
    # IDENTITY + BILATERAL CONTINUITY
    # --------------------------------
    IDENTITY_VERIFIED = "IDENTITY_VERIFIED"

    # ETK-S
    INTENT_LOCKED = "INTENT_LOCKED"

    # ETK-R
    RECEIVER_CONFIRMED = "RECEIVER_CONFIRMED"

    # RTT VERIFIED
    HANDSHAKE_VERIFIED = "HANDSHAKE_VERIFIED"

    # --------------------------------
    # ROUTE + EXECUTION DECISION
    # --------------------------------
    ROUTE_COMPUTED = "ROUTE_COMPUTED"

    PRICED = "PRICED"

    VALIDATED = "VALIDATED"

    # --------------------------------
    # EXECUTION PIPELINE
    # --------------------------------
    PENDING = "PENDING"

    DISPATCHED = "DISPATCHED"

    EXECUTION_STARTED = "EXECUTION_STARTED"

    EXECUTION_CONFIRMED = "EXECUTION_CONFIRMED"

    EXECUTION_FAILED = "EXECUTION_FAILED"

    # --------------------------------
    # FINALITY
    # --------------------------------
    SETTLED = "SETTLED"

    FINALIZED = "FINALIZED"

    # --------------------------------
    # FAILURE + REPLAY
    # --------------------------------
    FAILED = "FAILED"

    ROLLED_BACK = "ROLLED_BACK"

    REPLAY_REQUIRED = "REPLAY_REQUIRED"

    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"


# ==========================================
# VALID TRANSITIONS
# ==========================================
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
        TransactionState.PENDING,
        TransactionState.FAILED
    ],

    TransactionState.PENDING: [
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
        TransactionState.REPLAY_REQUIRED,
        TransactionState.ROLLED_BACK,
        TransactionState.FAILED
    ],

    TransactionState.REPLAY_REQUIRED: [
        TransactionState.EXECUTION_STARTED,
        TransactionState.RECONCILIATION_PENDING,
        TransactionState.FAILED
    ],

    TransactionState.RECONCILIATION_PENDING: [
        TransactionState.SETTLED,
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


# ==========================================
# CONTEXT OBJECT
# ==========================================
@dataclass
class TransactionContext:

    # --------------------------------
    # CORE CONTINUITY ATTRIBUTES
    # --------------------------------
    tx_id: str

    amount: float

    currency: str

    sender_id: str

    receiver_id: str

    # --------------------------------
    # CONTINUITY LINEAGE
    # --------------------------------
    continuity_id: Optional[str] = None

    lineage_parent: Optional[str] = None

    replay_generation: int = 0

    # --------------------------------
    # STATE
    # --------------------------------
    state: TransactionState = TransactionState.INIT

    updated_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc).isoformat()
        )
    )

    # --------------------------------
    # EXECUTION METADATA
    # --------------------------------
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ==========================================
    # STATE TRANSITION
    # ==========================================
    def transition(
        self,
        new_state: TransactionState,
        event_payload: Optional[Dict[str, Any]] = None
    ):

        allowed = VALID_TRANSITIONS.get(
            self.state,
            []
        )

        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: "
                f"{self.state} -> {new_state}"
            )

        old_state = self.state

        # --------------------------------
        # MUTATE CURRENT STATE
        # --------------------------------
        self.state = new_state

        self.updated_at = (
            datetime.now(timezone.utc).isoformat()
        )

        # --------------------------------
        # EMIT IMMUTABLE EVENT
        # --------------------------------
        emit_event(
            tx_id=self.tx_id,

            continuity_id=self.continuity_id,

            event_type="STATE_TRANSITION",

            previous_state=old_state.value,

            new_state=new_state.value,

            payload={
                "tx_id": self.tx_id,
                "continuity_id": self.continuity_id,
                "amount": self.amount,
                "currency": self.currency,
                "sender_id": self.sender_id,
                "receiver_id": self.receiver_id,
                "metadata": self.metadata,
                "event_payload": event_payload or {}
            },

            lineage_parent=self.lineage_parent,

            replay_generation=self.replay_generation
        )

        return self

    # ==========================================
    # ATTACH EXECUTION CONTEXT
    # ==========================================
    def attach(
        self,
        key: str,
        value: Any
    ):

        self.metadata[key] = value

        return self

    # ==========================================
    # REPLAY GENERATION BUMP
    # ==========================================
    def increment_replay_generation(self):

        self.replay_generation += 1

        return self

    # ==========================================
    # SERIALIZATION
    # ==========================================
    def to_dict(self):

        return {

            "tx_id": self.tx_id,

            "continuity_id": self.continuity_id,

            "lineage_parent": self.lineage_parent,

            "replay_generation": self.replay_generation,

            "amount": self.amount,

            "currency": self.currency,

            "sender_id": self.sender_id,

            "receiver_id": self.receiver_id,

            "state": self.state.value,

            "updated_at": self.updated_at,

            "metadata": self.metadata
        }