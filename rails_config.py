# ==============================
# rails_config.py
# ==============================

RAIL_CAPABILITIES = {
    "MPESA": ["KES", "TZS"],
    "AIRTEL": ["KES", "UGX", "TZS"],
    "BANK_KE": ["KES"],
    "BANK_UG": ["UGX"],
    "BANK_TZ": ["TZS"],
    "SMOVE": ["KES", "UGX", "TZS", "USD", "GBP", "NGN", "ZAR", "EGP"]
}


def supports_currency(rail: str, currency: str) -> bool:
    return currency in RAIL_CAPABILITIES.get(rail, [])


def get_rail(account_id: str) -> str:
    return account_id.split("-")[0]


def get_currency(account_id: str) -> str:
    return account_id.split("-")[-1]