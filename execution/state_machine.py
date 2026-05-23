# ==============================
# execution/state_machine.py
# RailOne Execution Continuity
# Deterministic Execution State Engine
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

from uuid import uuid4

from execution.event_emitter import emit_event


# ==========================================
# EXECUTION STATES
# ==========================================
class ExecutionState(str, Enum):

    # --------------------------------
    # EXECUTION INITIALIZATION
    # --------------------------------
    INIT = "INIT"

    # --------------------------------
    # IDENTITY + TRUST
    # --------------------------------
    IDENTITY_VERIFIED = (
        "IDENTITY_VERIFIED"
    )

    # ETK-S
    INTENT_LOCKED = (
        "INTENT_LOCKED"
    )

    # ETK-R
    RECEIVER_CONFIRMED = (
        "RECEIVER_CONFIRMED"
    )

    # RTT validated
    HANDSHAKE_VERIFIED = (
        "HANDSHAKE_VERIFIED"
    )

    # --------------------------------
    # ROUTING + PRICING
    # --------------------------------
    ROUTE_COMPUTED = (
        "ROUTE_COMPUTED"
    )

    PRICED = "PRICED"

    VALIDATED = "VALIDATED"

    # --------------------------------
    # EXECUTION PIPELINE
    # --------------------------------
    PENDING = "PENDING"

    DISPATCHED = "DISPATCHED"

    EXECUTION_STARTED = (
        "EXECUTION_STARTED"
    )

    EXECUTION_CONFIRMED = (
        "EXECUTION_CONFIRMED"
    )

    EXECUTION_FAILED = (
        "EXECUTION_FAILED"
    )

    # --------------------------------
    # REPLAY + RECOVERY
    # --------------------------------
    REPLAY_REQUIRED = (
        "REPLAY_REQUIRED"
    )

    RECONCILIATION_PENDING = (
        "RECONCILIATION_PENDING"
    )

    ROLLED_BACK = (
        "ROLLED_BACK"
    )

    # --------------------------------
    # FINALITY
    # --------------------------------
    SETTLED = "SETTLED"

    FINALIZED = "FINALIZED"

    FAILED = "FAILED"


# ==========================================
# VALID EXECUTION TRANSITIONS
# ==========================================
VALID_TRANSITIONS = {

    ExecutionState.INIT: [

        ExecutionState.IDENTITY_VERIFIED,

        ExecutionState.FAILED
    ],

    ExecutionState.IDENTITY_VERIFIED: [

        ExecutionState.INTENT_LOCKED,

        ExecutionState.FAILED
    ],

    ExecutionState.INTENT_LOCKED: [

        ExecutionState.RECEIVER_CONFIRMED,

        ExecutionState.FAILED
    ],

    ExecutionState.RECEIVER_CONFIRMED: [

        ExecutionState.HANDSHAKE_VERIFIED,

        ExecutionState.FAILED
    ],

    ExecutionState.HANDSHAKE_VERIFIED: [

        ExecutionState.ROUTE_COMPUTED,

        ExecutionState.FAILED
    ],

    ExecutionState.ROUTE_COMPUTED: [

        ExecutionState.PRICED,

        ExecutionState.FAILED
    ],

    ExecutionState.PRICED: [

        ExecutionState.VALIDATED,

        ExecutionState.FAILED
    ],

    ExecutionState.VALIDATED: [

        ExecutionState.PENDING,

        ExecutionState.FAILED
    ],

    ExecutionState.PENDING: [

        ExecutionState.DISPATCHED,

        ExecutionState.FAILED
    ],

    ExecutionState.DISPATCHED: [

        ExecutionState.EXECUTION_STARTED,

        ExecutionState.FAILED
    ],

    ExecutionState.EXECUTION_STARTED: [

        ExecutionState.EXECUTION_CONFIRMED,

        ExecutionState.EXECUTION_FAILED
    ],

    ExecutionState.EXECUTION_FAILED: [

        ExecutionState.REPLAY_REQUIRED,

        ExecutionState.ROLLED_BACK,

        ExecutionState.FAILED
    ],

    ExecutionState.REPLAY_REQUIRED: [

        ExecutionState.EXECUTION_STARTED,

        ExecutionState.RECONCILIATION_PENDING,

        ExecutionState.FAILED
    ],

    ExecutionState.RECONCILIATION_PENDING: [

        ExecutionState.SETTLED,

        ExecutionState.ROLLED_BACK,

        ExecutionState.FAILED
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
# Canonical execution continuity object
# ==========================================
@dataclass
class ExecutionContext:

    # --------------------------------
    # CANONICAL EXECUTION CONTINUITY
    # --------------------------------
    utt_id: str

    # --------------------------------
    # ROUTE REALIZATION THREAD
    # --------------------------------
    rtt_id: str

    # --------------------------------
    # IDENTITY CONTINUITY
    # --------------------------------
    continuity_uid: str

    # --------------------------------
    # EXECUTION ACTORS
    # --------------------------------
    sender_id: str

    receiver_id: str

    # --------------------------------
    # EXECUTION VALUE
    # --------------------------------
    amount: float

    currency: str

    # --------------------------------
    # EXECUTION LINEAGE
    # --------------------------------
    lineage_parent: Optional[str] = None

    replay_generation: int = 0

    # --------------------------------
    # EXECUTION STATE
    # --------------------------------
    state: ExecutionState = (
        ExecutionState.INIT
    )

    updated_at: str = field(

        default_factory=lambda:
            datetime.now(
                timezone.utc
            ).isoformat()
    )

    # --------------------------------
    # EXECUTION METADATA
    # --------------------------------
    metadata: Dict[str, Any] = field(

        default_factory=dict
    )

    # ==========================================
    # TRANSITION EXECUTION STATE
    # ==========================================
    def transition(

        self,

        new_state: ExecutionState,

        event_payload: Optional[
            Dict[str, Any]
        ] = None
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
        # MUTATE EXECUTION STATE
        # --------------------------------
        self.state = new_state

        self.updated_at = (

            datetime.now(
                timezone.utc
            ).isoformat()
        )

        # --------------------------------
        # EMIT EXECUTION EVENT
        # --------------------------------
        emit_event(

            utt_id=self.utt_id,

            rtt_id=self.rtt_id,

            continuity_uid=
                self.continuity_uid,

            event_type=
                "STATE_TRANSITION",

            previous_state=
                old_state.value,

            new_state=
                new_state.value,

            payload={

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

                "metadata":
                    self.metadata,

                "event_payload":
                    event_payload or {}
            },

            lineage_parent=
                self.lineage_parent,

            replay_generation=
                self.replay_generation
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

            "utt_id":
                self.utt_id,

            "rtt_id":
                self.rtt_id,

            "continuity_uid":
                self.continuity_uid,

            "lineage_parent":
                self.lineage_parent,

            "replay_generation":
                self.replay_generation,

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

            "updated_at":
                self.updated_at,

            "metadata":
                self.metadata
        }