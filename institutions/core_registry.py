# ==========================================
# core_registry.py
# RailOne Core Trust Registration
# ==========================================

from crypto.key_manager import (
    KeyManager
)

from crypto.keystore import (
    key_exists
)

from institutions.auth_registry import (
    INSTITUTION_REGISTRY
)


def register_core():

    institution_id = "R1CORE"

    if (
        institution_id
        not in INSTITUTION_REGISTRY
    ):

        raise Exception(
            "R1CORE_NOT_REGISTERED_"
            "IN_TRUST_REGISTRY"
        )

    if key_exists(
        institution_id
    ):

        print(
            "🔐 R1CORE already "
            "registered"
        )

        return

    KeyManager.ensure_institution_keys(
        institution_id
    )

    print(
        "🔐 R1CORE registered "
        "in execution trust layer"
    )