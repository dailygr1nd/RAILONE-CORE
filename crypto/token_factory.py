# ==========================================
# crypto/token_factory.py
# RailOne Trust Artifact Factory
# ==========================================

import hashlib
import json
import secrets
import time


class TokenFactory:

    # =====================================
    # INTERNAL HASH
    # =====================================
    @staticmethod
    def _hash(payload):

        if isinstance(payload, dict):

            payload = json.dumps(
                payload,
                sort_keys=True
            )

        return hashlib.sha256(
            payload.encode()
        ).hexdigest()

    # =====================================
    # CONTINUITY ANCHOR
    # =====================================
    @staticmethod
    def generate_continuity_anchor(
        continuity_uid
    ):

        payload = {

            "continuity_uid":
                continuity_uid,

            "anchor_nonce":
                secrets.token_hex(32),

            "timestamp":
                int(time.time())
        }

        continuity_anchor = (
            TokenFactory._hash(payload)
        )

        return {

            "continuity_anchor":
                continuity_anchor,

            "payload":
                payload
        }

    # =====================================
    # ETK-S
    # =====================================
    @staticmethod
    def generate_etk_s(

        sender_id,
        amount,
        currency
    ):

        payload = {

            "sender_id":
                sender_id,

            "amount":
                amount,

            "currency":
                currency,

            "entropy":
                secrets.token_hex(32),

            "timestamp":
                int(time.time())
        }

        etk_s = TokenFactory._hash(
            payload
        )

        return {

            "etk_s":
                etk_s,

            "payload":
                payload
        }

    # =====================================
    # ETK-R
    # =====================================
    @staticmethod
    def generate_etk_r(

        etk_s,
        receiver_id
    ):

        payload = {

            "etk_s":
                etk_s,

            "receiver_id":
                receiver_id,

            "timestamp":
                int(time.time())
        }

        etk_r = TokenFactory._hash(
            payload
        )

        return {

            "etk_r":
                etk_r,

            "payload":
                payload
        }

    # =====================================
    # UTT
    # Commercial Contract
    # =====================================
    @staticmethod
    def generate_utt(

        continuity_uid,

        quote_id,

        sender_id,

        receiver_id,

        amount,

        currency,

        routing_fee,

        max_attempts=5
    ):

        payload = {

            "continuity_uid":
                continuity_uid,

            "quote_id":
                quote_id,

            "sender_id":
                sender_id,

            "receiver_id":
                receiver_id,

            "amount":
                amount,

            "currency":
                currency,

            "routing_fee":
                routing_fee,

            "pricing_model":
                "PER_INTENT",

            "max_attempts":
                max_attempts,

            "timestamp":
                int(time.time())
        }

        utt_id = TokenFactory._hash(
            payload
        )

        return {

            "utt_id":
                utt_id,

            "payload":
                payload
        }

    # =====================================
    # RTT
    # Routing Attempt Artifact
    # =====================================
    @staticmethod
    def generate_rtt(

        utt_id,

        attempt,

        selected_route,

        route_score,

        previous_route=None
    ):

        payload = {

            "utt_id":
                utt_id,

            "attempt":
                attempt,

            "selected_route":
                selected_route,

            "previous_route":
                previous_route,

            "route_score":
                route_score,

            "tracking_nonce":
                secrets.token_hex(16),

            "timestamp":
                int(time.time())
        }

        rtt_id = TokenFactory._hash(
            payload
        )

        return {

            "rtt_id":
                rtt_id,

            "payload":
                payload
        }

    # =====================================
    # TOKEN EXPIRY
    # =====================================
    @staticmethod
    def is_expired(

        payload,
        ttl=60
    ):

        timestamp = payload.get(
            "timestamp"
        )

        if not timestamp:

            return False

        return (

            time.time()
            >
            (
                timestamp + ttl
            )
        )