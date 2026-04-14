# ==============================
# token_factory.py
# ==============================
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional


class TokenFactory:
    @staticmethod
    def _hash_128(payload: str) -> str:
        """Return 128-bit displayed hash (32 hex chars)."""
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    @staticmethod
    def generate_etk_s(sender_id: str, amount: float, timestamp: Optional[str] = None) -> str:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        nonce = secrets.token_hex(8)
        payload = f"ETK-S|{sender_id}|{amount}|{ts}|{nonce}"
        return TokenFactory._hash_128(payload)

    @staticmethod
    def generate_etk_r(etk_s: str, receiver_id: str) -> str:
        payload = f"ETK-R|{etk_s}|{receiver_id}"
        return TokenFactory._hash_128(payload)

    @staticmethod
    def generate_rtt(etk_s: str, etk_r: str, tx_context: str = "") -> str:
        payload = f"RTT|{etk_s}|{etk_r}|{tx_context}"
        return TokenFactory._hash_128(payload)

    @staticmethod
    def generate_utt(institution_id: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = secrets.token_hex(4).upper()
        return f"UTT-{institution_id}-{ts}-{suffix}"
