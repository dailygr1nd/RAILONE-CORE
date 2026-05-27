# ==========================================
# institutions/institution_base.py
# RailOne Institution Trust Domain
# ==========================================

from crypto.signer import (
    sign_payload
)

from crypto.verifier import (
    verify_signature
)


class InstitutionBase:

    def __init__(

        self,

        institution_id,

        institution_type,

        supported_adapters,

        supported_currencies,

        execution_policy,

        replay_policy,

        attestation_capable=False
    ):

        self.institution_id = (
            institution_id
        )

        self.institution_type = (
            institution_type
        )

        self.supported_adapters = (
            supported_adapters
        )

        self.supported_currencies = (
            supported_currencies
        )

        self.execution_policy = (
            execution_policy
        )

        self.replay_policy = (
            replay_policy
        )

        self.attestation_capable = (
            attestation_capable
        )

    # ======================================
    # EXECUTION CAPABILITY
    # ======================================
    def supports_adapter(
        self,
        adapter_type
    ):

        return (
            adapter_type
            in
            self.supported_adapters
        )

    def supports_currency(
        self,
        currency
    ):

        return (
            currency
            in
            self.supported_currencies
        )

    # ======================================
    # EXECUTION TRUST
    # ======================================
    def sign_execution_attestation(
        self,
        payload
    ):

        if not self.attestation_capable:

            raise Exception(
                "ATTESTATION_NOT_SUPPORTED"
            )

        return sign_payload(

            self.institution_id,

            payload
        )

    def verify_execution_signature(

        self,

        payload,

        signature
    ):

        return verify_signature(

            self.institution_id,

            payload,

            signature
        )

    # ======================================
    # EXECUTION POLICY
    # ======================================
    def requires_reconciliation(
        self
    ):

        return (
            self.replay_policy
            .get(
                "requires_reconciliation",
                False
            )
        )

    def max_retries(
        self
    ):

        return (
            self.replay_policy
            .get(
                "max_retries",
                0
            )
        )