# ==========================================
# institutions/auth_registry.py
# RailOne Execution Trust Registry
# ==========================================

from institutions.execution_capabilities import (
    EXECUTION_CAPABILITIES
)


INSTITUTION_REGISTRY = {

    institution_id: {

        **config,

        "trust_level":
            "HIGH",

        "attestation_capable":
            (
                config[
                    "institution_type"
                ]
                ==
                "BANK"
            ),

        "webhook_verification":
            True,

        "replay_policy": {

            "max_retries": 3,

            "requires_reconciliation":
                True,

            "manual_review_threshold":
                100000
        }
    }

    for (
        institution_id,
        config
    )

    in EXECUTION_CAPABILITIES.items()
}


# ==========================================
# LOOKUPS
# ==========================================
def get_institution(
    institution_id
):

    return INSTITUTION_REGISTRY.get(
        institution_id
    )


def get_supported_adapters(
    institution_id
):

    institution = get_institution(
        institution_id
    )

    if not institution:
        return []

    return institution.get(
        "supported_adapters",
        []
    )


def institution_supports_currency(

    institution_id,

    currency
):

    institution = get_institution(
        institution_id
    )

    if not institution:
        return False

    return (
        currency
        in
        institution.get(
            "supported_currencies",
            []
        )
    )


def institution_supports_replay(
    institution_id
):

    institution = get_institution(
        institution_id
    )

    if not institution:
        return False

    return institution.get(
        "supports_replay",
        False
    )


def institution_supports_adapter(

    institution_id,

    adapter
):

    institution = get_institution(
        institution_id
    )

    if not institution:
        return False

    return (
        adapter
        in
        institution.get(
            "supported_adapters",
            []
        )
    )