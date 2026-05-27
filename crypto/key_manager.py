# ==========================================
# crypto/key_manager.py
# RailOne Trust Key Manager
# ==========================================

from nacl.signing import (
    SigningKey
)

from nacl.encoding import (
    HexEncoder
)

from crypto.keystore import (
    store_keypair,
    load_keypair,
    key_exists
)

from institutions.auth_registry import (
    INSTITUTION_REGISTRY
)


class KeyManager:

    # ======================================
    # GENERATE KEYS
    # ======================================
    @staticmethod
    def generate_keypair():

        signing_key = SigningKey.generate()

        verify_key = (
            signing_key
            .verify_key
        )

        return {

            "private_key":

                signing_key.encode(
                    encoder=HexEncoder
                ).decode(),

            "public_key":

                verify_key.encode(
                    encoder=HexEncoder
                ).decode()
        }

    # ======================================
    # ENSURE INSTITUTION KEYS
    # ======================================
    @staticmethod
    def ensure_institution_keys(
        institution_id
    ):

        if key_exists(
            institution_id
        ):

            print(
                f"🔐 Loaded existing "
                f"keys for "
                f"{institution_id}"
            )

            return load_keypair(
                institution_id
            )

        keys = (
            KeyManager
            .generate_keypair()
        )

        institution = (
            INSTITUTION_REGISTRY
            .get(institution_id)
        )

        metadata = {

            "institution_type":

                institution.get(
                    "institution_type"
                ),

            "supported_adapters":

                institution.get(
                    "supported_adapters"
                ),

            "attestation_capable":

                institution.get(
                    "attestation_capable"
                ),

            "key_purpose":
                "EXECUTION_SIGNING"
        }

        store_keypair(

            institution_id,

            keys["private_key"],

            keys["public_key"],

            metadata
        )

        print(
            f"🔐 Generated new "
            f"keys for "
            f"{institution_id}"
        )

        return load_keypair(
            institution_id
        )