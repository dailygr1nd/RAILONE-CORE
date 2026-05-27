# ==========================================
# institutions/institution_router.py
# RailOne Execution Capability Router
# ==========================================

from institutions.auth_registry import (
    INSTITUTION_REGISTRY
)


class InstitutionRouter:

    def __init__(self):

        self.registry = (
            INSTITUTION_REGISTRY
        )

    def select_institution(

        self,

        currency,

        country,

        execution_mode
    ):

        candidates = []

        for (
            institution_id,
            config
        ) in self.registry.items():

            if (
                currency
                not in config[
                    "supported_currencies"
                ]
            ):

                continue

            if (
                country
                != config["country"]
            ):

                continue

            if (
                execution_mode
                not in config[
                    "execution_modes"
                ]
            ):

                continue

            candidates.append({

                "institution_id":
                    institution_id,

                "trust_level":
                    config[
                        "trust_level"
                    ],

                "supported_adapters":
                    config[
                        "supported_adapters"
                    ],

                "execution_policy":
                    config[
                        "execution_policy"
                    ]
            })

        if not candidates:

            raise Exception(
                "NO_EXECUTION_DOMAIN_FOUND"
            )

        return candidates[0]

    def get_supported_adapters(
        self,
        institution_id
    ):

        institution = (
            self.registry.get(
                institution_id
            )
        )

        if not institution:
            return []

        return institution.get(
            "supported_adapters",
            []
        )