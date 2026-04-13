# bank_tz_ke.py (PRODUCTION V3)
from user_accounts import get_accounts

def _process_bank_rail(amount, route, rail_name):
    sender = route.get("sender")
    account_id = route.get("account")
    hold_mode = route.get("hold_mode", True)

    accounts = get_accounts(sender["nid"], rail_name)

    if not accounts:
        return {
            "success": False,
            "Reason": f"No {rail_name} accounts found",
            "Rail": rail_name,
        }

    if account_id not in accounts:
        return {
            "success": False,
            "Reason": "Invalid account selected",
            "Rail": rail_name,
        }

    account = accounts[account_id]

    # Production flow: funds already held upstream
    if hold_mode:
        return {
            "success": True,
            "Status": "Executed",
            "Rail": rail_name,
            "SettlementMode": "HELD_COMMIT",
        }

    # Direct debit mode
    if account["balance"] < amount:
        return {
            "success": False,
            "Reason": "Insufficient funds",
            "Rail": rail_name,
        }

    account["balance"] -= amount

    return {
        "success": True,
        "Status": "Executed",
        "Rail": rail_name,
        "SettlementMode": "DIRECT_DEBIT",
    }


def process_bank_tz(amount, route, daily_totals=None):
    """TZ accounts (formerly BANK_A)"""
    return _process_bank_rail(amount, route, "BANK_TZ")


def process_bank_ke(amount, route, daily_totals=None):
    """KE accounts (formerly BANK_B)"""
    return _process_bank_rail(amount, route, "BANK_KE")