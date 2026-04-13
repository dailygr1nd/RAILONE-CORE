# ==========================
# legacy_bank.py (PRODUCTION V2)
# Hold-aware institution connector
# ==========================
from user_accounts import get_accounts


def process(amount, route, daily_totals=None):
    """
    Legacy bank institution connector.
    IMPORTANT: does NOT debit again if funds are already held
    by transaction_engine.
    """

    sender = route.get("sender")
    account_id = route.get("account")
    hold_mode = route.get("hold_mode", True)

    accounts = get_accounts(sender["nid"], "BANK")

    if not accounts:
        return {
            "success": False,
            "Reason": "No BANK accounts found",
        }

    if account_id not in accounts:
        return {
            "success": False,
            "Reason": "Invalid account selected",
        }

    account = accounts[account_id]

    # In production flow funds are already HELD upstream
    if hold_mode:
        return {
            "success": True,
            "Status": "Executed",
            "SettlementMode": "HELD_COMMIT",
        }

    # Fallback for legacy simulation flow
    if account["balance"] < amount:
        return {
            "success": False,
            "Reason": "Insufficient funds",
        }

    account["balance"] -= amount

    return {
        "success": True,
        "Status": "Executed",
        "SettlementMode": "DIRECT_DEBIT",
    }
