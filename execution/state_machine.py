## ==========================================
# execution/state_machine.py
# RailOne UTT Lifecycle Engine
# ==========================================

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
    Any
)

from execution.event_store import (
    emit_event
)

from execution.checkpoint_engine import (
    create_checkpoint
)


# ==========================================
# UTT STATES
# ==========================================
class UTTState(str, Enum):

    CREATED = "CREATED"

    PROCESSING = "PROCESSING"

    RETRYING = "RETRYING"

    FINALIZED = "FINALIZED"

    FAILED = "FAILED"


# ==========================================
# VALID TRANSITIONS
# ==========================================
VALID_TRANSITIONS = {

    UTTState.CREATED: [

        UTTState.PROCESSING,

        UTTState.FAILED
    ],

    UTTState.PROCESSING: [

        UTTState.RETRYING,

        UTTState.FINALIZED,

        UTTState.FAILED
    ],

    UTTState.RETRYING: [

        UTTState.PROCESSING,

        UTTState.FINALIZED,

        UTTState.FAILED
    ],

    UTTState.FINALIZED: [],

    UTTState.FAILED: []
}


# ==========================================
# EXECUTION CONTEXT
# ==========================================
@dataclass
class ExecutionContext:

    utt_id: str

    continuity_uid: str

    sender_id: str

    receiver_id: str

    amount: float

    currency: str

    state: UTTState = (
        UTTState.CREATED
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

        self.publish(
            event_payload
        )

        self.checkpoint()

        return self

    # ======================================
    # CHECKPOINT
    # ======================================
    def checkpoint(self):

        create_checkpoint(

            utt_id=
                self.utt_id,

            continuity_uid=
                self.continuity_uid,

            checkpoint_state=
                self.state.value,

            snapshot=
                self.to_dict()
        )

    # ======================================
    # PUBLISH
    # ======================================
    def publish(

        self,

        event_payload=None
    ):

        emit_event(

            utt_id=
                self.utt_id,

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
    # SERIALIZE
    # ======================================
    def to_dict(self):

        return {

            "utt_id":
                self.utt_id,

            "continuity_uid":
                self.continuity_uid,

            "sender_id":
                self.sender_id,

            "receiver_id":
                self.receiver_id,

            "amount":
                self.amount,

            "currency":
                self.currency,

            "state":
                self.state.value,

            "updated_at":
                self.updated_at,

            "metadata":
                self.metadata
        }