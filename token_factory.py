# ==============================
# token_factory.py (FINAL v2)
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
    # HASH
    # --------------------------------
    @staticmethod
    def _hash_128(payload: str) -> str:
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

        keys = TrustRegistry.get_all_keys(institution_id)

        for key_entry in keys:
            public_key = key_entry["public_key"]

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
        return f"{institution_id}-RN-{secrets.token_hex(3).upper()}"

    # --------------------------------
    # ETK-S
    # --------------------------------
    @staticmethod
    def generate_etk_s(sender_id, amount, institution_id):
        ts = datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_hex(8)

        payload = f"ETK-S|{sender_id}|{amount}|{ts}|{nonce}"

        return (
            TokenFactory._hash_128(payload),
            TokenFactory.sign(payload, institution_id),
            payload
        )

    # --------------------------------
    # ETK-R
    # --------------------------------
    @staticmethod
    def generate_etk_r(etk_s, receiver_id, institution_id):
        payload = f"ETK-R|{etk_s}|{receiver_id}"

        return (
            TokenFactory._hash_128(payload),
            TokenFactory.sign(payload, institution_id),
            payload
        )

    # --------------------------------
    # RTT
    # --------------------------------
    @staticmethod
    def generate_rtt(etk_s, etk_r, tx_id, institution_id):
        payload = f"RTT|{etk_s}|{etk_r}|{tx_id}"

        return (
            TokenFactory._hash_128(payload),
            TokenFactory.sign(payload, institution_id),
            payload
        )

    # --------------------------------
    # UTT
    # --------------------------------
    @staticmethod
    def generate_utt(institution_id):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = secrets.token_hex(4).upper()

        return f"UTT-{institution_id}-{ts}-{suffix}"