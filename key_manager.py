# ==============================
# key_manager.py (ROTATION READY)
# ==============================

from cryptography.hazmat.primitives.asymmetric import rsa
from trust_registry import TrustRegistry


class KeyManager:

    _private_keys = {}

    @staticmethod
    def onboard_institution(institution_id):

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        public_key = private_key.public_key()

        KeyManager._private_keys[institution_id] = private_key

        TrustRegistry.register_institution(
            institution_id,
            public_key
        )

        return public_key

    @staticmethod
    def rotate_keys(institution_id):

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        public_key = private_key.public_key()

        KeyManager._private_keys[institution_id] = private_key

        TrustRegistry.rotate_key(institution_id, public_key)

    @staticmethod
    def get_private_key(institution_id):
        return KeyManager._private_keys[institution_id]

    @staticmethod
    def get_public_key(institution_id):
        return TrustRegistry.get_public_key(institution_id)