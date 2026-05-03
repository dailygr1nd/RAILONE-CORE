# ==============================
# token_factory.py (PRODUCTION READY)
# ==============================

import hashlib
import secrets
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from key_manager import KeyManager
from trust_registry import TrustRegistry


class TokenFactory:

    # --------------------------------
    # HASH (128-bit display)
    # --------------------------------
    @staticmethod
    def _hash(payload: str) -> str:
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    # --------------------------------
    # SIGN
    # --------------------------------
    @staticmethod
    def sign(payload: str, institution_id: str) -> bytes:
        private_key = KeyManager.get_private_key(institution_id)

        return private_key.sign(
            payload.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

    # --------------------------------
    # VERIFY (MULTI-KEY SUPPORT)
    # --------------------------------
    @staticmethod
    def verify(payload: str, signature: bytes, institution_id: str) -> bool:
        keys = TrustRegistry.get_valid_public_keys(institution_id)

        for public_key in keys:
            try:
                public_key.verify(
                    signature,
                    payload.encode(),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True
            except Exception:
                continue

        return False

    # --------------------------------
    # TX ID
    # --------------------------------
    @staticmethod
    def generate_tx_id(institution_id: str) -> str:
        suffix = secrets.token_hex(3).upper()
        return f"{institution_id}-RN-{suffix}"

    # --------------------------------
    # ETK-S
    # --------------------------------
    @staticmethod
    def generate_etk_s(sender_id, amount, institution_id):
        ts = datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_hex(8)

        payload = f"ETK-S|{sender_id}|{amount}|{ts}|{nonce}"
        token = TokenFactory._hash(payload)
        signature = TokenFactory.sign(payload, institution_id)

        return token, signature, payload

    # --------------------------------
    # ETK-R
    # --------------------------------
    @staticmethod
    def generate_etk_r(etk_s, receiver_id, institution_id):
        payload = f"ETK-R|{etk_s}|{receiver_id}"
        token = TokenFactory._hash(payload)
        signature = TokenFactory.sign(payload, institution_id)

        return token, signature, payload

    # --------------------------------
    # RTT
    # --------------------------------
    @staticmethod
    def generate_rtt(etk_s, etk_r, tx_id, institution_id):
        payload = f"RTT|{etk_s}|{etk_r}|{tx_id}"
        token = TokenFactory._hash(payload)
        signature = TokenFactory.sign(payload, institution_id)

        return token, signature, payload

        # --------------------------------
    # UTT
    # --------------------------------
    @staticmethod
    def generate_utt(institution_id):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = secrets.token_hex(4).upper()
        return f"UTT-{institution_id}-{ts}-{suffix}"

    # --------------------------------
    # TIMESTAMP EXTRACTION
    # --------------------------------
    @staticmethod
    def extract_timestamp(payload: str):
        try:
            parts = payload.split("|")
            for p in parts:
                if "T" in p and ":" in p:
                    return datetime.fromisoformat(p)
        except Exception:
            return None

    # --------------------------------
    # EXPIRY CHECK
    # --------------------------------
    @staticmethod
    def is_expired(payload: str, ttl_seconds: int = 300) -> bool:
        """
        Checks if token payload timestamp is expired.
        """

        try:
            parts = payload.split("|")

            if len(parts) < 4:
                return True

            ts = parts[3]

            token_time = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)

            age = (now - token_time).total_seconds()

            return age > ttl_seconds

        except Exception:
            return True