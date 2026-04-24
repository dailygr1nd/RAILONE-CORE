# ==============================
# auth_registry.py (PROD READY BASE)
# ==============================

INSTITUTIONS = {
    "bank_ke": {
        "api_key": "rk_live_bank_ke",
        "api_secret": "sk_live_bank_ke",
        "rate_limit_per_min": 60
    },
    "mpesa": {
        "api_key": "rk_live_mpesa",
        "api_secret": "sk_live_mpesa",
        "rate_limit_per_min": 120
    },
    "smove": {
        "api_key": "rk_live_smove",
        "api_secret": "sk_live_smove",
        "rate_limit_per_min": 200
    }
}


# --------------------------------
# LOOKUP BY API KEY
# --------------------------------
def get_institution_by_key(api_key: str):
    for inst, data in INSTITUTIONS.items():
        if data["api_key"] == api_key:
            return inst, data
    return None, None


# --------------------------------
# GET SECRET
# --------------------------------
def get_secret(api_key: str):
    _, data = get_institution_by_key(api_key)
    return data["api_secret"] if data else None


# --------------------------------
# GET RATE LIMIT
# --------------------------------
def get_rate_limit(api_key: str):
    _, data = get_institution_by_key(api_key)
    return data["rate_limit_per_min"] if data else 0