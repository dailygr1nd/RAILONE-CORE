# ==============================
# core_registry.py (ALIGNED)
# ==============================

from key_manager import KeyManager


def register_core():

    institution_id = "R1CORE"

    # 🔐 onboard like any other institution
    if institution_id not in KeyManager._private_keys:
        KeyManager.onboard_institution(institution_id)
        print("🔐 R1CORE registered in cryptographic layer")
    else:
        print("🔐 R1CORE already registered")