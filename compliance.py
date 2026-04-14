# compliance.py

from rules import (
    get_tier_limits,
    requires_enhanced_due_diligence,
    is_high_risk_corridor,
)

BLACKLISTED_IDS = {
    "10000999",
}

PEP_IDS = {
    "10001000",
}


class ComplianceEngine:
    def __init__(self):
        self.daily_totals = {}
        self.alert_queue = []

    # -------------------------
    # SANCTIONS / BLACKLIST
    # -------------------------
    def check_blacklist(self, nid):
        if nid in BLACKLISTED_IDS:
            return False, "SANCTIONS_BLOCK"
        return True, None

    # -------------------------
    # PEP CHECK
    # -------------------------
    def check_pep(self, nid):
        if nid in PEP_IDS:
            return True, "PEP_REVIEW_REQUIRED"
        return True, None

    # -------------------------
    # TIER LIMIT CHECK
    # -------------------------
    def check_limits(self, sender, amount):
        tier = sender["attestation"]["kyc_level"]
        limits = get_tier_limits(tier)

        if amount > limits["single_tx"]:
            return False, "SINGLE_TX_LIMIT_EXCEEDED"

        current = self.daily_totals.get(
            sender["username"],
            0,
        )

        if current + amount > limits["daily_total"]:
            return False, "DAILY_LIMIT_EXCEEDED"

        return True, None

    # -------------------------
    # CROSS-BORDER RISK
    # -------------------------
    def check_corridor_risk(
        self,
        sender_currency,
        receiver_currency,
        amount,
    ):
        if is_high_risk_corridor(
            sender_currency,
            receiver_currency,
        ):
            self.raise_alert(
                "HIGH_RISK_CORRIDOR",
                {
                    "amount": amount,
                    "from": sender_currency,
                    "to": receiver_currency,
                },
            )

        if requires_enhanced_due_diligence(amount):
            return False, "EDD_REQUIRED"

        return True, None

    # -------------------------
    # ALERT MANAGEMENT
    # -------------------------
    def raise_alert(self, code, payload):
        self.alert_queue.append({
            "alert_code": code,
            "payload": payload,
        })

    # -------------------------
    # UPDATE TOTALS
    # -------------------------
    def update_totals(self, sender, amount):
        username = sender["username"]
        self.daily_totals[username] = (
            self.daily_totals.get(username, 0)
            + amount
        )