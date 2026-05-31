# ==============================
# execution/continuity_envelope.py
# RailOne Execution Continuity Envelope
# ==============================

import hashlib
import json
import time

from typing import (
    Dict,
    Any,
    Optional,
    List
)


class ContinuityEnvelope:

    # ======================================
    # INIT
    # ======================================
    def __init__(

        self,

        utt_id,

        continuity_uid,

        sender_id,

        receiver_id,

        amount,

        currency,

        rtt_id=None,

        etk_s=None,

        etk_r=None,

        lineage_parent=None,

        replay_generation=0
    ):

        self.utt_id = utt_id

        self.continuity_uid = (
            continuity_uid
        )

        self.sender_id = sender_id

        self.receiver_id = receiver_id

        self.amount = amount

        self.currency = currency

        self.rtt_id = rtt_id

        self.etk_s = etk_s

        self.etk_r = etk_r

        self.lineage_parent = (
            lineage_parent
        )

        self.replay_generation = (
            replay_generation
        )

        self.created_at = (
            time.time()
        )

        self.updated_at = (
            self.created_at
        )

        self.metadata = {}

        self.attestations = []

        self.quote = None

        self.route = None

        self.provider = None

        self.provider_reference = None

        self.settlement_reference = None

    # ======================================
    # ENVELOPE HASH
    # ======================================
    def envelope_hash(self):

        payload = {

            "utt_id":
                self.utt_id,

            "rtt_id":
                self.rtt_id,

            "etk_s":
                self.etk_s,

            "etk_r":
                self.etk_r,

            "continuity_uid":
                self.continuity_uid,

            "sender_id":
                self.sender_id,

            "receiver_id":
                self.receiver_id,

            "amount":
                self.amount,

            "currency":
                self.currency
        }

        return hashlib.sha256(

            json.dumps(
                payload,
                sort_keys=True
            ).encode()

        ).hexdigest()

    # ======================================
    # ATTACH QUOTE
    # ======================================
    def attach_quote(

        self,

        quote
    ):

        self.quote = quote

        self.updated_at = (
            time.time()
        )

    # ======================================
    # ATTACH ROUTE
    # ======================================
    def attach_route(

        self,

        route
    ):

        self.route = route

        self.updated_at = (
            time.time()
        )

    # ======================================
    # ATTACH PROVIDER
    # ======================================
    def attach_provider(

        self,

        provider,

        provider_reference=None
    ):

        self.provider = provider

        self.provider_reference = (
            provider_reference
        )

        self.updated_at = (
            time.time()
        )

    # ======================================
    # ATTACH SETTLEMENT
    # ======================================
    def attach_settlement_reference(

        self,

        settlement_reference
    ):

        self.settlement_reference = (
            settlement_reference
        )

        self.updated_at = (
            time.time()
        )

    # ======================================
    # ATTACH METADATA
    # ======================================
    def attach(

        self,

        key,

        value
    ):

        self.metadata[key] = value

        self.updated_at = (
            time.time()
        )

    # ======================================
    # ADD ATTESTATION
    # ======================================
    def add_attestation(

        self,

        institution_id,

        signature,

        attestation_type
    ):

        self.attestations.append({

            "institution_id":
                institution_id,

            "attestation_type":
                attestation_type,

            "signature":
                signature,

            "timestamp":
                time.time()
        })

        self.updated_at = (
            time.time()
        )

    # ======================================
    # REPLAY CLONE
    # ======================================
    def create_replay_child(self):

        return ContinuityEnvelope(

            utt_id=self.utt_id,

            continuity_uid=
                self.continuity_uid,

            sender_id=
                self.sender_id,

            receiver_id=
                self.receiver_id,

            amount=
                self.amount,

            currency=
                self.currency,

            rtt_id=
                self.rtt_id,

            etk_s=
                self.etk_s,

            etk_r=
                self.etk_r,

            lineage_parent=
                self.utt_id,

            replay_generation=
                self.replay_generation + 1
        )

    # ======================================
    # SUMMARY
    # ======================================
    def summary(self):

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

            "provider":
                self.provider,

            "attestations":
                len(self.attestations),

            "replay_generation":
                self.replay_generation,

            "hash":
                self.envelope_hash()
        }

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

            "sender_id":
                self.sender_id,

            "receiver_id":
                self.receiver_id,

            "amount":
                self.amount,

            "currency":
                self.currency,

            "etk_s":
                self.etk_s,

            "etk_r":
                self.etk_r,

            "lineage_parent":
                self.lineage_parent,

            "replay_generation":
                self.replay_generation,

            "provider":
                self.provider,

            "provider_reference":
                self.provider_reference,

            "settlement_reference":
                self.settlement_reference,

            "quote":
                self.quote,

            "route":
                self.route,

            "metadata":
                self.metadata,

            "attestations":
                self.attestations,

            "created_at":
                self.created_at,

            "updated_at":
                self.updated_at,

            "envelope_hash":
                self.envelope_hash()
        }