# ==============================
# key_manager.py (TRUST + ROTATION READY)
# ==============================

from cryptography.hazmat.primitives.asymmetric import rsa
from trust_registry import TrustRegistry


class KeyManager:
    """
    Handles:
    - private key storage (local)
    - public key registration (via TrustRegistry)
    - key rotation
    """

    _private_keys = {}

    # --------------------------------
    # ONBOARD INSTITUTION (PRIMARY ENTRY)
    # --------------------------------
    @staticmethod
    def onboard_institution(institution_id: str):
        """
        Creates key pair + registers public key in trust registry
        """

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        public_key = private_key.public_key()

        KeyManager._private_keys[institution_id] = private_key

        # Register with trust registry
        TrustRegistry.register_institution(
            institution_id,
            public_key
        )

        return public_key

    # --------------------------------
    # INTERNAL KEY GENERATION (SAFE WRAPPER)
    # --------------------------------
    @staticmethod
    def generate_key_pair(institution_id: str):
        """
        Ensures institution is fully onboarded
        """
        if institution_id in KeyManager._private_keys:
            return

        KeyManager.onboard_institution(institution_id)

    # --------------------------------
    # KEY ROTATION
    # --------------------------------
    @staticmethod
    def rotate_keys(institution_id: str):
        """
        Rotate key pair and update trust registry
        """

        if institution_id not in KeyManager._private_keys:
            raise Exception(f"Institution not onboarded: {institution_id}")

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        public_key = private_key.public_key()

        KeyManager._private_keys[institution_id] = private_key

        TrustRegistry.rotate_key(
            institution_id,
            public_key
        )

        print(f"🔄 Keys rotated for {institution_id}")

    # --------------------------------
    # GET PRIVATE KEY
    # --------------------------------
    @staticmethod
    def get_private_key(institution_id: str):
        if institution_id not in KeyManager._private_keys:
            raise KeyError(f"Institution not registered: {institution_id}")

        return KeyManager._private_keys[institution_id]

    # --------------------------------
    # GET PUBLIC KEY (FROM TRUST REGISTRY)
    # --------------------------------
    @staticmethod
    def get_public_key(institution_id: str):
        return TrustRegistry.get_public_key(institution_id)


# ==============================
# BOOTSTRAP TRUST REGISTRY
# ==============================
def bootstrap_institutions():
    """
    Initializes core rails into trust network
    """

    institutions = [
        "MPESA",
        "BANK_KE",
        "BANK_UG",
        "BANK_TZ",
        "SMOVE"
    ]

    for inst in institutions:
        if inst not in KeyManager._private_keys:
            KeyManager.onboard_institution(inst)
            print(f"🔐 Registered institution: {inst}")


# AUTO-BOOTSTRAP ON IMPORT
bootstrap_institutions()