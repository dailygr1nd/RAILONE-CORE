# ==============================
# liquidity_pools.py (CORRIDOR BASED)
# ==============================

POOLS = {

    # Weak corridor
    "KES_TZS": {
        "balance": 100_000,
        "capacity": 500_000
    },

    # Strong corridor
    "KES_UGX": {
        "balance": 1_000_000,
        "capacity": 2_000_000
    },

    "UGX_TZS": {
        "balance": 800_000,
        "capacity": 1_500_000
    },

    # fallback FX
    "USD_KES": {
        "balance": 500_000,
        "capacity": 1_000_000
    }
}