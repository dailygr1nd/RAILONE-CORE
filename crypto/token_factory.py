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
    # ETK-S
    # Execution Trust Key (Sender)
    # =====================================
    @staticmethod
    def generate_etk_s(

        sender_railone_id,
        amount,
        currency
    ):

        payload = {

            "sender":
                sender_railone_id,

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
    # Derived from ETK-S
    # =====================================
    @staticmethod
    def generate_etk_r(

        etk_s,
        receiver_railone_id
    ):

        payload = {

            "etk_s":
                etk_s,

            "receiver":
                receiver_railone_id,

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
    # RTT
    # Derived from ETK-S + ETK-R
    # =====================================
    @staticmethod
    def generate_rtt(

        etk_s,
        etk_r
    ):

        payload = {

            "etk_s":
                etk_s,

            "etk_r":
                etk_r,

            "tracking_nonce":
                secrets.token_hex(16),

            "timestamp":
                int(time.time())
        }

        rtt = TokenFactory._hash(
            payload
        )

        return {

            "rtt":
                rtt,

            "payload":
                payload
        }

    # =====================================
    # UTT
    # Derived after quote acceptance
    # =====================================
    @staticmethod
    def generate_utt(

        rtt,
        etk_s,
        etk_r,
        quote_id,
        accepted_quote
    ):

        quote_hash = hashlib.sha256(

            json.dumps(
                accepted_quote,
                sort_keys=True
            ).encode()

        ).hexdigest()

        payload = {

            "rtt":
                rtt,

            "etk_s":
                etk_s,

            "etk_r":
                etk_r,

            "quote_id":
                quote_id,

            "quote_hash":
                quote_hash,

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
    # CONTINUITY ANCHOR
    # Identity continuity root
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

        anchor = TokenFactory._hash(
            payload
        )

        return {

            "continuity_anchor":
                anchor,

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
            (timestamp + ttl)
        )