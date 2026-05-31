# ==============================
# execution/state_machine.py
# RailOne Execution Continuity
# Deterministic State Engine
# ==============================

from enum import Enum

from dataclasses import (
    dataclass,
    field
)

from datetime import (
    datetime,
    timezone
)

from typing import (
    Dict,
    Any,
    Optional
)

from execution.event_store import emit_event

from execution.checkpoint_engine import (
    create_checkpoint
)


# ==========================================
# EXECUTION STATES
# ==========================================
class ExecutionState(str, Enum):

    INIT = "INIT"

    IDENTITY_VERIFIED = "IDENTITY_VERIFIED"

    INTENT_LOCKED = "INTENT_LOCKED"

    RECEIVER_CONFIRMED = "RECEIVER_CONFIRMED"

    HANDSHAKE_VERIFIED = "HANDSHAKE_VERIFIED"

    ROUTE_COMPUTED = "ROUTE_COMPUTED"

    PRICED = "PRICED"

    VALIDATED = "VALIDATED"

    PENDING = "PENDING"

    DISPATCHED = "DISPATCHED"

    EXECUTION_STARTED = "EXECUTION_STARTED"

    EXECUTION_CONFIRMED = "EXECUTION_CONFIRMED"

    EXECUTION_FAILED = "EXECUTION_FAILED"

    REPLAY_REQUIRED = "REPLAY_REQUIRED"

    RECONCILIATION_PENDING = (
        "RECONCILIATION_PENDING"
    )

    ROLLED_BACK = "ROLLED_BACK"

    SETTLED = "SETTLED"

    FINALIZED = "FINALIZED"

    FAILED = "FAILED"


# ==========================================
# PUBLISHED STATES ONLY
# ==========================================
PUBLISHABLE_STATES = {

    ExecutionState.PENDING,

    ExecutionState.EXECUTION_STARTED,

    ExecutionState.EXECUTION_CONFIRMED,

    ExecutionState.EXECUTION_FAILED,

    ExecutionState.REPLAY_REQUIRED,

    ExecutionState.SETTLED,

    ExecutionState.FINALIZED
}


# ==========================================
# VALID TRANSITIONS
# ==========================================
VALID_TRANSITIONS = {

    ExecutionState.INIT: [
        ExecutionState.IDENTITY_VERIFIED,
        ExecutionState.FAILED
    ],

    ExecutionState.IDENTITY_VERIFIED: [
        ExecutionState.INTENT_LOCKED
    ],

    ExecutionState.INTENT_LOCKED: [
        ExecutionState.RECEIVER_CONFIRMED
    ],

    ExecutionState.RECEIVER_CONFIRMED: [
        ExecutionState.HANDSHAKE_VERIFIED
    ],

    ExecutionState.HANDSHAKE_VERIFIED: [
        ExecutionState.ROUTE_COMPUTED
    ],

    ExecutionState.ROUTE_COMPUTED: [
        ExecutionState.PRICED
    ],

    ExecutionState.PRICED: [
        ExecutionState.VALIDATED
    ],

    ExecutionState.VALIDATED: [
        ExecutionState.PENDING
    ],

    ExecutionState.PENDING: [
        ExecutionState.DISPATCHED,
        ExecutionState.FAILED
    ],

    ExecutionState.DISPATCHED: [
        ExecutionState.EXECUTION_STARTED
    ],

    ExecutionState.EXECUTION_STARTED: [
        ExecutionState.EXECUTION_CONFIRMED,
        ExecutionState.EXECUTION_FAILED
    ],

    ExecutionState.EXECUTION_FAILED: [
        ExecutionState.REPLAY_REQUIRED,
        ExecutionState.ROLLED_BACK
    ],

    ExecutionState.REPLAY_REQUIRED: [
        ExecutionState.EXECUTION_STARTED,
        ExecutionState.RECONCILIATION_PENDING
    ],

    ExecutionState.RECONCILIATION_PENDING: [
        ExecutionState.SETTLED,
        ExecutionState.ROLLED_BACK
    ],

    ExecutionState.EXECUTION_CONFIRMED: [
        ExecutionState.SETTLED
    ],

    ExecutionState.SETTLED: [
        ExecutionState.FINALIZED
    ],

    ExecutionState.FINALIZED: [],

    ExecutionState.FAILED: [
        ExecutionState.ROLLED_BACK
    ],

    ExecutionState.ROLLED_BACK: []
}


# ==========================================
# EXECUTION CONTEXT
# ==========================================
@dataclass
class ExecutionContext:

    utt_id: str

    rtt_id: str

    continuity_uid: str

    sender_id: str

    receiver_id: str

    amount: float

    currency: str

    lineage_parent: Optional[str] = None

    replay_generation: int = 0

    state: ExecutionState = (
        ExecutionState.INIT
    )

    updated_at: str = field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ======================================
    # TRANSITION
    # ======================================
    def transition(

        self,

        new_state,

        event_payload=None
    ):

        allowed = VALID_TRANSITIONS.get(
            self.state,
            []
        )

        if new_state not in allowed:

            raise ValueError(

                f"Invalid transition "

                f"{self.state.value}"

                f" -> "

                f"{new_state.value}"
            )

        self.state = new_state

        self.updated_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        if self.should_publish():

            self.publish(
                event_payload
            )

        if self.should_checkpoint():

            self.checkpoint()

        return self

    # ======================================
    # PUBLISH DECISION
    # ======================================
    def should_publish(self):

        return (
            self.state
            in
            PUBLISHABLE_STATES
        )

    # ======================================
    # CHECKPOINT DECISION
    # ======================================
    def should_checkpoint(self):

        return self.state in {

            ExecutionState.PENDING,

            ExecutionState.EXECUTION_CONFIRMED,

            ExecutionState.EXECUTION_FAILED,

            ExecutionState.SETTLED,

            ExecutionState.FINALIZED
        }

    # ======================================
    # CHECKPOINT
    # ======================================
    def checkpoint(self):

        create_checkpoint(

            utt_id=self.utt_id,

            rtt_id=self.rtt_id,

            continuity_uid=
                self.continuity_uid,

            checkpoint_state=
                self.state.value,

            snapshot=
                self.to_dict(),

            lineage_parent=
                self.lineage_parent,

            replay_generation=
                self.replay_generation
        )

    # ======================================
    # PUBLISH
    # ======================================
    def publish(

        self,

        event_payload=None
    ):

        emit_event(

            utt_id=self.utt_id,

            rtt_id=self.rtt_id,

            continuity_uid=
                self.continuity_uid,

            event_type=
                self.state.value,

            canonical_state=
                self.state.value,

            payload={

                "amount":
                    self.amount,

                "currency":
                    self.currency,

                "sender_id":
                    self.sender_id,

                "receiver_id":
                    self.receiver_id,

                "metadata":
                    self.metadata,

                "event_payload":
                    event_payload or {}
            }
        )

    # ======================================
    # ATTACH
    # ======================================
    def attach(

        self,

        key,

        value
    ):

        self.metadata[key] = value

        return self

    # ======================================
    # REPLAY BUMP
    # ======================================
    def increment_replay_generation(self):

        self.replay_generation += 1

        return self

    # ======================================
    # SERIALIZE
    # ======================================
    def to_dict(self):

        return {

            "utt_id":
                self.utt_id,

            "rtt_id":
                self.rtt_id,

            "continuity_uid":
                self.continuity_uid,

            "amount":
                self.amount,

            "currency":
                self.currency,

            "sender_id":
                self.sender_id,

            "receiver_id":
                self.receiver_id,

            "state":
                self.state.value,

            "lineage_parent":
                self.lineage_parent,

            "replay_generation":
                self.replay_generation,

            "updated_at":
                self.updated_at,

            "metadata":
                self.metadata
        }