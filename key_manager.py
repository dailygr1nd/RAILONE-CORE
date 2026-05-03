# ==============================
# key_manager.py (PERSISTENT + TRUST + ROTATION READY)
# ==============================

from cryptography.hazmat.primitives.asymmetric import rsa
from trust_registry import TrustRegistry
from keystore import save_private_key, load_private_key


class KeyManager:
    """
    Handles:
    - private key storage (in-memory + persistent)
    - public key registration (via TrustRegistry)
    - key rotation
    """

    _private_keys = {}

    # --------------------------------
    # ONBOARD INSTITUTION (PRIMARY ENTRY)
    # --------------------------------
    @staticmethod
    def onboard_institution(institution_id: str):

        # 🔥 1. Try load from persistent store
        existing = load_private_key(institution_id)

        if existing:
            KeyManager._private_keys[institution_id] = existing

            TrustRegistry.register_institution(
                institution_id,
                existing.public_key()
            )

            print(f"🔐 Loaded existing keys for {institution_id}")
            return existing.public_key()

        # 🔥 2. Otherwise generate new key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        public_key = private_key.public_key()

        # 🔥 3. Store in memory
        KeyManager._private_keys[institution_id] = private_key

        # 🔥 4. Persist to disk
        save_private_key(institution_id, private_key)

        # 🔥 5. Register public key
        TrustRegistry.register_institution(
            institution_id,
            public_key
        )

        print(f"🔐 Institution onboarded: {institution_id}")

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

        # 🔥 Update memory
        KeyManager._private_keys[institution_id] = private_key

        # 🔥 Persist new key
        save_private_key(institution_id, private_key)

        # 🔥 Update trust registry
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

        if institution_id in KeyManager._private_keys:
            return KeyManager._private_keys[institution_id]

        # 🔥 fallback to persistent load
        existing = load_private_key(institution_id)

        if existing:
            KeyManager._private_keys[institution_id] = existing
            return existing

        raise KeyError(f"Institution not registered: {institution_id}")

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
        KeyManager.generate_key_pair(inst)
        print(f"🔐 Registered institution: {inst}")


# AUTO-BOOTSTRAP ON IMPORT
bootstrap_institutions()