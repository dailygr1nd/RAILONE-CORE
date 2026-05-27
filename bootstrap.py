# ==========================================
# bootstrap.py
# RailOne System Bootstrap
# ==========================================

from ledger.bootstrap import (bootstrap_institutions)

from institutions.core_registry import (register_core)

from crypto.key_manager import (KeyManager)

from institutions.auth_registry import (INSTITUTION_REGISTRY)


def bootstrap():

    print(
        "🔧 Bootstrapping RailOne..."
    )

    # ======================================
    # INSTITUTION REGISTRATION
    # ======================================
    bootstrap_institutions()

    # ======================================
    # CRYPTOGRAPHIC TRUST LAYER
    # ======================================
    for institution_id in (
        INSTITUTION_REGISTRY.keys()
    ):

        KeyManager.ensure_institution_keys(
            institution_id
        )

    # ======================================
    # CORE REGISTRATION
    # ======================================
    register_core()

    print(
        "✅ RailOne bootstrap complete"
    )