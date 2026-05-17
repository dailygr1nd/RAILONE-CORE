# ==============================
# settlement_capacity_signals.py (CORRIDOR BASED)
# ==============================

POOLS = {

    # Weak corridor
    "KES_TZS": {
        "mirrored_available_state": 100_000,
        "capacity": 500_000
    },

    # Strong corridor
    "KES_UGX": {
        "mirrored_available_state": 1_000_000,
        "capacity": 2_000_000
    },

    "UGX_TZS": {
        "mirrored_available_state": 800_000,
        "capacity": 1_500_000
    },

    # fallback FX
    "USD_KES": {
        "mirrored_available_state": 500_000,
        "capacity": 1_000_000
    }
}