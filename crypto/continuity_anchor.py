# ==========================================
# crypto/continuity_anchor.py
# RailOne Continuity Anchor Engine
# ==========================================

import json
import hashlib

from datetime import datetime


class ContinuityAnchor:

    # ======================================
    # CANONICAL SERIALIZATION
    # ======================================
    @staticmethod
    def _canonicalize(payload):

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":")
        )

    # ======================================
    # HASH
    # ======================================
    @staticmethod
    def _hash(payload):

        return hashlib.sha256(
            payload.encode()
        ).hexdigest()

    # ======================================
    # GENERATE CONTINUITY ANCHOR
    # ======================================
    @staticmethod
    def generate(

        continuity_uid,

        etk_s,

        etk_r,

        rtt_id,

        utt_id,

        replay_generation=0,

        route_generation=0,

        checkpoint_hash=None,

        parent_anchor=None,

        provider_reference=None
    ):

        payload = {

            # ==========================
            # IDENTITY CONTINUITY
            # ==========================
            "continuity_uid":
                continuity_uid,

            # ==========================
            # TRUST ARTIFACTS
            # ==========================
            "etk_s":
                etk_s,

            "etk_r":
                etk_r,

            # ==========================
            # EXECUTION CONTINUITY
            # ==========================
            "rtt_id":
                rtt_id,

            "utt_id":
                utt_id,

            # ==========================
            # LINEAGE
            # ==========================
            "replay_generation":
                replay_generation,

            "route_generation":
                route_generation,

            # ==========================
            # CHECKPOINTING
            # ==========================
            "checkpoint_hash":
                checkpoint_hash,

            # ==========================
            # PARENT CONTINUITY
            # ==========================
            "parent_anchor":
                parent_anchor,

            # ==========================
            # PROVIDER CORRELATION
            # ==========================
            "provider_reference":
                provider_reference
        }

        canonical = (
            ContinuityAnchor
            ._canonicalize(payload)
        )

        anchor = (
            ContinuityAnchor
            ._hash(canonical)
        )

        return {

            "anchor":
                anchor,

            "payload":
                payload,

            "generated_at":
                datetime.utcnow()
                .isoformat()
        }

    # ======================================
    # VERIFY ANCHOR
    # ======================================
    @staticmethod
    def verify(

        expected_anchor,

        payload
    ):

        canonical = (
            ContinuityAnchor
            ._canonicalize(payload)
        )

        computed = (
            ContinuityAnchor
            ._hash(canonical)
        )

        return (
            computed
            ==
            expected_anchor
        )

    # ======================================
    # REPLAY DERIVATION
    # ======================================
    @staticmethod
    def derive_replay_anchor(

        previous_anchor,

        replay_generation,

        checkpoint_hash
    ):

        payload = {

            "previous_anchor":
                previous_anchor,

            "replay_generation":
                replay_generation,

            "checkpoint_hash":
                checkpoint_hash
        }

        canonical = (
            ContinuityAnchor
            ._canonicalize(payload)
        )

        return (
            ContinuityAnchor
            ._hash(canonical)
        )

    # ======================================
    # DIVERGENCE CHECK
    # ======================================
    @staticmethod
    def detect_divergence(

        anchor_a,

        anchor_b
    ):

        return (
            anchor_a
            !=
            anchor_b
        )

    # ======================================
    # CHECKPOINT ANCHOR
    # ======================================
    @staticmethod
    def derive_checkpoint_anchor(

        utt_id,

        checkpoint_hash,

        execution_state
    ):

        payload = {

            "utt_id":
                utt_id,

            "checkpoint_hash":
                checkpoint_hash,

            "execution_state":
                execution_state
        }

        canonical = (
            ContinuityAnchor
            ._canonicalize(payload)
        )

        return (
            ContinuityAnchor
            ._hash(canonical)
        )

    # ======================================
    # EXECUTION LINEAGE PROOF
    # ======================================
    @staticmethod
    def build_lineage_proof(

        continuity_uid,

        anchors
    ):

        payload = {

            "continuity_uid":
                continuity_uid,

            "anchor_chain":
                anchors
        }

        canonical = (
            ContinuityAnchor
            ._canonicalize(payload)
        )

        lineage_root = (
            ContinuityAnchor
            ._hash(canonical)
        )

        return {

            "lineage_root":
                lineage_root,

            "anchors":
                anchors
        }