# ==========================================
# crypto/trust_registry.py
# RailOne Trust Registry
# ==========================================

from datetime import datetime

from crypto.keystore import (
    load_keypair,
    get_public_key,
    key_exists
)

from institutions.auth_registry import (
    INSTITUTION_REGISTRY
)


class TrustRegistry:

    # ======================================
    # INSTITUTION EXISTS
    # ======================================
    @staticmethod
    def institution_exists(
        institution_id
    ):

        return (
            institution_id
            in
            INSTITUTION_REGISTRY
        )

    # ======================================
    # TRUSTED INSTITUTION
    # ======================================
    @staticmethod
    def is_trusted(
        institution_id
    ):

        if not (
            TrustRegistry
            .institution_exists(
                institution_id
            )
        ):
            return False

        return key_exists(
            institution_id
        )

    # ======================================
    # ACTIVE PUBLIC KEY
    # ======================================
    @staticmethod
    def get_public_key(
        institution_id
    ):

        if not (
            TrustRegistry
            .is_trusted(
                institution_id
            )
        ):

            raise Exception(
                "UNTRUSTED_INSTITUTION"
            )

        return get_public_key(
            institution_id
        )

    # ======================================
    # KEYPAIR METADATA
    # ======================================
    @staticmethod
    def get_key_metadata(
        institution_id
    ):

        keypair = load_keypair(
            institution_id
        )

        if not keypair:
            return None

        return keypair.get(
            "metadata",
            {}
        )

    # ======================================
    # TRUST STATUS
    # ======================================
    @staticmethod
    def get_trust_status(
        institution_id
    ):

        if not (
            TrustRegistry
            .institution_exists(
                institution_id
            )
        ):

            return "UNKNOWN"

        if not key_exists(
            institution_id
        ):

            return "UNTRUSTED"

        return "TRUSTED"

    # ======================================
    # EXECUTION ATTESTATION
    # ======================================
    @staticmethod
    def supports_attestation(
        institution_id
    ):

        institution = (
            INSTITUTION_REGISTRY
            .get(
                institution_id
            )
        )

        if not institution:
            return False

        return institution.get(
            "attestation_capable",
            False
        )

    # ======================================
    # EXECUTION TRUST PROFILE
    # ======================================
    @staticmethod
    def get_trust_profile(
        institution_id
    ):

        institution = (
            INSTITUTION_REGISTRY
            .get(
                institution_id
            )
        )

        if not institution:

            raise Exception(
                "UNKNOWN_INSTITUTION"
            )

        metadata = (
            TrustRegistry
            .get_key_metadata(
                institution_id
            )
        )

        return {

            "institution_id":
                institution_id,

            "trust_status":

                TrustRegistry
                .get_trust_status(
                    institution_id
                ),

            "attestation_capable":

                institution.get(
                    "attestation_capable",
                    False
                ),

            "supported_adapters":

                institution.get(
                    "supported_adapters",
                    []
                ),

            "supported_currencies":

                institution.get(
                    "supported_currencies",
                    []
                ),

            "key_metadata":
                metadata,

            "validated_at":

                datetime.utcnow()
                .isoformat()
        }