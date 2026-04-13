# ==========================
# bank_a.py / bank_b.py (PRODUCTION V2)
# Hold-aware institution connectors
# ==========================
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

    # Production flow: already held upstream
    if hold_mode:
        return {
            "success": True,
            "Status": "Executed",
            "Rail": rail_name,
            "SettlementMode": "HELD_COMMIT",
        }

    # Legacy fallback mode
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


def process_bank_a(amount, route, daily_totals=None):
    return _process_bank_rail(amount, route, "BANK_A")


def process_bank_b(amount, route, daily_totals=None):
    return _process_bank_rail(amount, route, "BANK_B")


# ==========================
# psp.py (MOBILE MONEY | EA PRODUCTION V2)
# ==========================
import time
from compliance import check_tier, check_blacklist

PSP_NAME = "MOBILE_MONEY"

SUPPORTED_NETWORKS = {
    "AIRTEL_MONEY": ["TZ", "KE", "UG"],
    "MPESA": ["KE", "TZ"],
}

NETWORK_SPEED = {
    "AIRTEL_MONEY": 0.4,
    "MPESA": 0.3,
}


def resolve_mobile_network(route):
    destination = route.get("destination")
    preferred_network = route.get("network")

    if preferred_network:
        return preferred_network

    # Auto corridor selection
    if destination in ["KE", "TZ"]:
        return "MPESA"

    if destination in ["UG"]:
        return "AIRTEL_MONEY"

    return None


def process(amount, route):
    sender = route["sender"]
    sender_id = sender["nid"]

    network = resolve_mobile_network(route)
    destination = route.get("destination")

    if not network:
        return {
            "success": False,
            "Status": "Failed",
            "Reason": "NO_NETWORK_AVAILABLE",
            "Rail": PSP_NAME,
        }

    if destination not in SUPPORTED_NETWORKS.get(network, []):
        return {
            "success": False,
            "Status": "Failed",
            "Reason": f"{network}_UNSUPPORTED_CORRIDOR",
            "Rail": PSP_NAME,
        }

    # --------------------------
    # COMPLIANCE
    # --------------------------
    ok, error = check_blacklist(sender_id)
    if not ok:
        return {
            "success": False,
            "Status": "Failed",
            "Reason": error,
            "Rail": network,
        }

    ok, error = check_tier(sender, amount)
    if not ok:
        return {
            "success": False,
            "Status": "Failed",
            "Reason": error,
            "Rail": network,
        }

    # --------------------------
    # NETWORK LATENCY SIMULATION
    # --------------------------
    time.sleep(NETWORK_SPEED.get(network, 0.5))

    # --------------------------
    # TTL / SESSION EXPIRY
    # --------------------------
    if route.get("ttl") and time.time() > route["ttl"]:
        return {
            "success": False,
            "Status": "Failed",
            "Reason": "TTL_EXPIRED",
            "Rail": network,
        }

    return {
        "success": True,
        "Status": "Executed",
        "Rail": network,
        "Corridor": destination,
    }
