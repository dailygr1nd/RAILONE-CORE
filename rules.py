# rules.py

# ---------------------------------
# EAST AFRICA POLICY RULES
# ---------------------------------

TIER_LIMITS = {
    "TIER_1": {
        "single_tx": 50000,
        "daily_total": 100000,
        "monthly_total": 500000,
    },
    "TIER_2": {
        "single_tx": 500000,
        "daily_total": 1000000,
        "monthly_total": 5000000,
    },
    "TIER_3": {
        "single_tx": 5000000,
        "daily_total": 10000000,
        "monthly_total": 50000000,
    },
}

HIGH_RISK_CORRIDORS = {
    ("KES", "USD"),
    ("TZS", "USD"),
    ("UGX", "USD"),
}

SUSPICIOUS_AMOUNT_THRESHOLD = 1000000


def get_tier_limits(kyc_level):
    return TIER_LIMITS.get(
        kyc_level,
        TIER_LIMITS["TIER_1"],
    )


def requires_enhanced_due_diligence(amount):
    return amount >= SUSPICIOUS_AMOUNT_THRESHOLD


def is_high_risk_corridor(sender_currency, receiver_currency):
    return (
        sender_currency,
        receiver_currency,
    ) in HIGH_RISK_CORRIDORS