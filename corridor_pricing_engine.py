# ==============================
# corridor_pricing_engine.py (CLEAN)
# ==============================

"""
This module handles FEES only.
FX pricing is handled in fx_engine.
"""

BASE_FEES = {
    "BANK": 1500,
    "PSP": 500,
    "SMOVE": 750
}


def get_route_fee(route_type: str):

    if "BANK" in route_type:
        return BASE_FEES["BANK"]

    elif "PSP" in route_type:
        return BASE_FEES["PSP"]

    else:
        return BASE_FEES["SMOVE"]


def calculate_pricing(amount, route_type):

    """
    Rules:
    - Fees are applied on source currency
    - FX handled separately
    """

    fee = get_route_fee(route_type)

    net_amount = round(amount - fee, 2)

    if net_amount <= 0:
        return {
            "error": "INVALID_NET_AMOUNT",
            "route_fee": fee,
            "net_amount": 0
        }

    return {
        "route_fee": fee,
        "net_amount": net_amount
    }