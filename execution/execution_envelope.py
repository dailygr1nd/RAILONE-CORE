# ==============================
# continuity_envelope.py
# RailOne Continuity Envelope
# Deterministic Execution
# Continuity Object
# ==============================

import hashlib
import json
import time
import uuid

from typing import Dict, Any, List, Optional

from execution.state_machine import ExecutionState


# ==========================================
# CONTINUITY ENVELOPE
# ==========================================
class ContinuityEnvelope:

    # ==========================================
    # INIT
    # ==========================================
    def __init__(
        self,
        payload: Dict[str, Any],
        continuity_uid: Optional[str] = None,
        lineage_parent: Optional[str] = None,
        replay_generation: int = 0
    ):

        # --------------------------------
        # EXECUTION ATTEMPT ID
        # --------------------------------
        self.utt_id = (
            f"R1EXEC-{uuid.uuid4().hex[:12].upper()}"
        )

        # --------------------------------
        # CONTINUITY LINEAGE ID
        # --------------------------------
        if not continuity_uid:

           raise ValueError(
               "continuity_uid required"
            )

        self.continuity_uid = (
            continuity_uid)

        # --------------------------------
        # LINEAGE ANCESTRY
        # --------------------------------
        self.lineage_parent = lineage_parent

        self.replay_generation = replay_generation

        # --------------------------------
        # TIMESTAMPS
        # --------------------------------
        self.created_at = time.time()

        self.updated_at = self.created_at

        # --------------------------------
        # PAYLOAD
        # --------------------------------
        self.payload = payload

        self.payload_hash = (
            self._hash_payload(payload)
        )

        # --------------------------------
        # EXECUTION STATE
        # --------------------------------
        self.state = ExecutionState.INIT.value

        # --------------------------------
        # BILATERAL ATTESTATIONS
        # --------------------------------
        self.attestations: List[Dict[str, Any]] = []

        # --------------------------------
        # CANONICAL CONTINUITY HISTORY
        # --------------------------------
        self.history: List[Dict[str, Any]] = []

        # --------------------------------
        # REPLAY CHECKPOINTS
        # --------------------------------
        self.replay_checkpoints: List[Dict[str, Any]] = []

        # --------------------------------
        # EXECUTION EVENTS
        # --------------------------------
        self.events: List[Dict[str, Any]] = []

        # --------------------------------
        # EXECUTION METADATA
        # --------------------------------
        self.metadata: Dict[str, Any] = {}

        # --------------------------------
        # ROUTE CONTEXT
        # --------------------------------
        self.route_reference = None

        self.corridor = None

        self.execution_profile = None

        self.route_confidence = None

        # --------------------------------
        # SETTLEMENT REFERENCES
        # --------------------------------
        self.settlement_reference = None

        self.execution_reference = None

        # --------------------------------
        # RTT + ETK REFERENCES
        # --------------------------------
        self.rtt_id = None

        self.etk_s = None

        self.etk_r = None

        # --------------------------------
        # INITIAL EVENT
        # --------------------------------
        self._record_event(
            event_type="CONTINUITY_CREATED",
            payload={
                "utt_id": self.utt_id,
                "continuity_uid": self.continuity_uid
            }
        )

    # ==========================================
    # HASH PAYLOAD
    # ==========================================
    def _hash_payload(
        self,
        payload: Dict[str, Any]
    ) -> str:

        encoded = json.dumps(
            payload,
            sort_keys=True
        ).encode()

        return hashlib.sha256(
            encoded
        ).hexdigest()

    # ==========================================
    # RECORD EVENT
    # ==========================================
    def _record_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None
    ):

        event = {

            "event_id": (
                f"EV-{uuid.uuid4().hex[:12].upper()}"
            ),

            "event_type": event_type,

            "utt_id": self.utt_id,

            "continuity_uid": self.continuity_uid,

            "lineage_parent": self.lineage_parent,

            "replay_generation": self.replay_generation,

            "timestamp": time.time(),

            "payload": payload or {}
        }

        self.events.append(event)

        self.updated_at = time.time()

    # ==========================================
    # STATE TRANSITION
    # ==========================================
    def set_state(
        self,
        new_state: str,
        reason: Optional[str] = None
    ):

        previous_state = self.state

        self.history.append({

            "from": previous_state,

            "to": new_state,

            "timestamp": time.time(),

            "reason": reason
        })

        self.state = new_state

        self.updated_at = time.time()

        self._record_event(
            event_type="STATE_TRANSITION",
            payload={
                "previous_state": previous_state,
                "new_state": new_state,
                "reason": reason
            }
        )

    # ==========================================
    # ATTACH METADATA
    # ==========================================
    def attach(
        self,
        key: str,
        value: Any
    ):

        self.metadata[key] = value

        self.updated_at = time.time()

        self._record_event(
            event_type="METADATA_ATTACHED",
            payload={
                "key": key,
                "value": value
            }
        )

    # ==========================================
    # ADD ATTESTATION
    # ==========================================
    def add_attestation(
        self,
        party: str,
        attestation_type: str,
        signature: str
    ):

        attestation = {

            "party": party,

            "type": attestation_type,

            "signature": signature,

            "timestamp": time.time()
        }

        self.attestations.append(
            attestation
        )

        self.updated_at = time.time()

        self._record_event(
            event_type="ATTESTATION_ADDED",
            payload=attestation
        )

    # ==========================================
    # CHECK ATTESTATION
    # ==========================================
    def has_attestation(
        self,
        attestation_type: str
    ) -> bool:

        return any(
            a["type"] == attestation_type
            for a in self.attestations
        )

    # ==========================================
    # CREATE REPLAY CHECKPOINT
    # ==========================================
    def create_replay_checkpoint(
        self,
        checkpoint_type: str,
        payload: Optional[Dict[str, Any]] = None
    ):

        checkpoint = {

            "checkpoint_id": (
                f"CHK-{uuid.uuid4().hex[:12].upper()}"
            ),

            "checkpoint_type": checkpoint_type,

            "utt_id": self.utt_id,

            "continuity_uid": self.continuity_uid,

            "timestamp": time.time(),

            "state": self.state,

            "payload": payload or {}
        }

        self.replay_checkpoints.append(
            checkpoint
        )

        self.updated_at = time.time()

        self._record_event(
            event_type="REPLAY_CHECKPOINT_CREATED",
            payload=checkpoint
        )

    # ==========================================
    # REPLAY GENERATION BUMP
    # ==========================================
    def increment_replay_generation(self):

        self.replay_generation += 1

        self.updated_at = time.time()

        self._record_event(
            event_type="REPLAY_GENERATION_INCREMENTED",
            payload={
                "replay_generation": (
                    self.replay_generation
                )
            }
        )

    # ==========================================
    # ROUTE CONTEXT
    # ==========================================
    def attach_route_context(
        self,
        route_reference: str,
        corridor: str,
        execution_profile: str,
        route_confidence: float
    ):

        self.route_reference = route_reference

        self.corridor = corridor

        self.execution_profile = (
            execution_profile
        )

        self.route_confidence = (
            route_confidence
        )

        self.updated_at = time.time()

        self._record_event(
            event_type="ROUTE_CONTEXT_ATTACHED",
            payload={
                "route_reference": route_reference,
                "corridor": corridor,
                "execution_profile": execution_profile,
                "route_confidence": route_confidence
            }
        )

    # ==========================================
    # SETTLEMENT REFERENCES
    # ==========================================
    def attach_settlement_reference(
        self,
        settlement_reference: str,
        execution_reference: str
    ):

        self.settlement_reference = (
            settlement_reference
        )

        self.execution_reference = (
            execution_reference
        )

        self.updated_at = time.time()

        self._record_event(
            event_type="SETTLEMENT_REFERENCE_ATTACHED",
            payload={
                "settlement_reference":
                    settlement_reference,

                "execution_reference":
                    execution_reference
            }
        )

    # ==========================================
    # RTT + ETK REFERENCES
    # ==========================================
    def attach_execution_attestations(
        self,
        rtt: str,
        etk_s: str,
        etk_r: str
    ):

        self.rtt_id = rtt

        self.etk_s = etk_s

        self.etk_r = etk_r

        self.updated_at = time.time()

        self._record_event(
            event_type="EXECUTION_ATTESTATIONS_ATTACHED",
            payload={
                "rtt": rtt,
                "etk_s": etk_s,
                "etk_r": etk_r
            }
        )

    # ==========================================
    # SUMMARY
    # ==========================================
    def get_summary(self):

        return {

            "utt_id": self.utt_id,

            "continuity_uid":
                self.continuity_uid,

            "lineage_parent":
                self.lineage_parent,

            "replay_generation":
                self.replay_generation,

            "state": self.state,

            "payload_hash":
                self.payload_hash,

            "attestation_count":
                len(self.attestations),

            "event_count":
                len(self.events),

            "checkpoint_count":
                len(self.replay_checkpoints),

            "created_at":
                self.created_at,

            "updated_at":
                self.updated_at
        }

    # ==========================================
    # SERIALIZATION
    # ==========================================
    def to_dict(self):

        return {

            "utt_id": self.utt_id,

            "continuity_uid":
                self.continuity_uid,

            "lineage_parent":
                self.lineage_parent,

            "replay_generation":
                self.replay_generation,

            "created_at":
                self.created_at,

            "updated_at":
                self.updated_at,

            "state":
                self.state,

            "payload":
                self.payload,

            "payload_hash":
                self.payload_hash,

            "metadata":
                self.metadata,

            "attestations":
                self.attestations,

            "history":
                self.history,

            "events":
                self.events,

            "replay_checkpoints":
                self.replay_checkpoints,

            "route_reference":
                self.route_reference,

            "corridor":
                self.corridor,

            "execution_profile":
                self.execution_profile,

            "route_confidence":
                self.route_confidence,

            "settlement_reference":
                self.settlement_reference,

            "execution_reference":
                self.execution_reference,

            "rtt":
                self.rtt_id,

            "etk_s":
                self.etk_s,

            "etk_r":
                self.etk_r
        }