# rules.py

def get_tier_limits(tier):
    tiers = {
        "LOW": {"single_tx": 50_000, "daily_total": 100_000},
        "MEDIUM": {"single_tx": 200_000, "daily_total": 500_000},
        "HIGH": {"single_tx": 1_000_000, "daily_total": 5_000_000},
    }
    return tiers.get(tier, tiers["LOW"])


def requires_enhanced_due_diligence(amount):
    return amount > 500_000


def is_high_risk_corridor(from_ccy, to_ccy):
    high_risk = [
        ("USD", "NGN"),
        ("USD", "EGP"),
    ]
    return (from_ccy, to_ccy) in high_risk