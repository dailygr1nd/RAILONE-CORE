# compliance.py

from identity_db import IDENTITY_DB

# --------------------------
# BLACKLISTED USERS
# --------------------------
BLACKLISTED_IDS = set([
    # Example: "10000999"
])

# --------------------------
# TIER LIMITS
# --------------------------
TIER_LIMITS = {
    "TIER_1": 100000,
    "TIER_2": 1000000,
    "TIER_3": 10000000
}

# --------------------------
# CHECK TIER
# --------------------------
def check_tier(sender, amount):
    tier = sender.get("attestation", {}).get("kyc_level", "TIER_1")
    limit = TIER_LIMITS.get(tier, 1000)
    if amount > limit:
        return False, f"TIER_LIMIT_EXCEEDED ({tier} max {limit})"
    return True, None

# --------------------------
# CHECK BLACKLIST
# --------------------------
def check_blacklist(nid):
    if nid in BLACKLISTED_IDS:
        return False, "BLACKLISTED_USER"
    return True, None

# --------------------------
# CHECK DAILY TOTAL
# --------------------------
def check_daily_limit(sender, amount, daily_totals):
    """
    daily_totals: dict mapping username -> cumulative amount
    """
    tier = sender.get("attestation", {}).get("kyc_level", "TIER_1")
    limit = TIER_LIMITS.get(tier, 1000)
    current_total = daily_totals.get(sender["username"], 0)
    if current_total + amount > limit:
        return False, f"DAILY_LIMIT_EXCEEDED ({current_total + amount}/{limit})"
    return True, None

# --------------------------
# UPDATE DAILY TOTAL
# --------------------------
def update_daily_total(sender, amount, daily_totals):
    daily_totals[sender["username"]] = daily_totals.get(sender["username"], 0) + amount