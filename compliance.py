# compliance.py
# FIX: _engine was previously instantiated inside the class body,
# making it a class-level variable inaccessible at module scope.
# Module-level functions (check_blacklist, etc.) referenced _engine
# at module scope — a NameError at runtime. Fixed by moving
# instantiation to after the class definition.

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
    def check_blacklist(self, national_id):
        if national_id in BLACKLISTED_IDS:
            return False, "SANCTIONS_BLOCK"
        return True, None

    # -------------------------
    # PEP CHECK
    # -------------------------
    def check_pep(self, national_id):
        if national_id in PEP_IDS:
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

        current = self.daily_totals.get(sender["username"], 0)

        if current + amount > limits["daily_total"]:
            return False, "DAILY_LIMIT_EXCEEDED"

        return True, None

    # -------------------------
    # CROSS-BORDER RISK
    # -------------------------
    def check_corridor_risk(self, sender_currency, receiver_currency, amount):
        if is_high_risk_corridor(sender_currency, receiver_currency):
            self.raise_alert(
                "HIGH_RISK_CORRIDOR",
                {"amount": amount, "from": sender_currency, "to": receiver_currency},
            )

        if requires_enhanced_due_diligence(amount):
            return False, "EDD_REQUIRED"

        return True, None

    # -------------------------
    # ALERT MANAGEMENT
    # -------------------------
    def raise_alert(self, code, payload):
        self.alert_queue.append({"alert_code": code, "payload": payload})

    def flush_alerts(self):
        alerts = list(self.alert_queue)
        self.alert_queue.clear()
        return alerts

    # -------------------------
    # UPDATE TOTALS
    # -------------------------
    def update_totals(self, sender, amount):
        username = sender["username"]
        self.daily_totals[username] = self.daily_totals.get(username, 0) + amount


# -------------------------------------------------------
# MODULE-LEVEL SINGLETON
# FIX: previously instantiated INSIDE the class body —
# Python scopes that as a class attribute, not a module
# variable. Moved here so all module-level functions below
# can reference it without NameError.
# -------------------------------------------------------
_engine = ComplianceEngine()


def check_blacklist(national_id):
    return _engine.check_blacklist(national_id)


def check_pep(national_id):
    return _engine.check_pep(national_id)


def check_tier(sender, amount):
    return _engine.check_limits(sender, amount)


def check_daily_limit(sender, amount, daily_totals):
    _engine.daily_totals = daily_totals
    return _engine.check_limits(sender, amount)


def check_corridor_risk(sender_currency, receiver_currency, amount):
    return _engine.check_corridor_risk(sender_currency, receiver_currency, amount)


def update_daily_total(sender, amount, daily_totals):
    _engine.update_totals(sender, amount)
    daily_totals.update(_engine.daily_totals)


def get_compliance_alerts():
    return _engine.flush_alerts()