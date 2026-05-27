# ==========================================
# crypto/auth_engine.py
# RailOne Continuity Authentication Engine
# ==========================================

import time
import hashlib

from crypto.signer import (
    sign_payload
)

from crypto.verifier import (
    verify_signature
)


class AuthEngine:

    ALLOWED_CLOCK_DRIFT = 60

    # ======================================
    # CREATE AUTH HEADER
    # ======================================
    @staticmethod
    def create_auth_payload(

        institution_id,

        continuity_uid,

        utt_id,

        replay_generation,

        payload
    ):

        timestamp = int(
            time.time()
        )

        auth_payload = {

            "institution_id":
                institution_id,

            "continuity_uid":
                continuity_uid,

            "utt_id":
                utt_id,

            "replay_generation":
                replay_generation,

            "timestamp":
                timestamp,

            "payload":
                payload
        }

        signature = sign_payload(

            institution_id,

            auth_payload
        )

        return {

            "auth_payload":
                auth_payload,

            "signature":
                signature
        }

    # ======================================
    # VERIFY AUTH PAYLOAD
    # ======================================
    @staticmethod
    def verify_auth_payload(

        institution_id,

        auth_payload,

        signature
    ):

        timestamp = (
            auth_payload
            .get("timestamp")
        )

        current_time = int(
            time.time()
        )

        if (
            abs(
                current_time
                - timestamp
            )
            >
            AuthEngine
            .ALLOWED_CLOCK_DRIFT
        ):

            raise Exception(
                "AUTH_TIMESTAMP_EXPIRED"
            )

        verified = verify_signature(

            institution_id,

            auth_payload,

            signature
        )

        if not verified:

            raise Exception(
                "INVALID_SIGNATURE"
            )

        return True

    # ======================================
    # REPLAY HASH
    # ======================================
    @staticmethod
    def generate_replay_hash(
        payload
    ):

        payload_str = str(
            payload
        )

        return hashlib.sha256(

            payload_str.encode()

        ).hexdigest()