# ==============================
# corridor_pricing_engine.py
# ==============================

"""
Corridor pricing layer.

Handles:
- rail access cost
- corridor premium
- urgency pricing

FX handled separately.
"""


# --------------------------------
# BASE RAIL COSTS
# --------------------------------
RAIL_COSTS = {
    "BANK": 1500,
    "PSP": 500,
    "SMOVE": 750
}


# --------------------------------
# CORRIDOR PREMIUMS
# --------------------------------
CORRIDOR_PREMIUMS = {
    "KES_UGX": 200,
    "KES_TZS": 150,
    "USD_KES": 400
}


# --------------------------------
# RAIL COST
# --------------------------------
def get_rail_cost(route_type):

    if "BANK" in route_type:
        return RAIL_COSTS["BANK"]

    elif "PSP" in route_type:
        return RAIL_COSTS["PSP"]

    return RAIL_COSTS["SMOVE"]


# --------------------------------
# CORRIDOR PREMIUM
# --------------------------------
def get_corridor_premium(currency_pair):

    return CORRIDOR_PREMIUMS.get(
        currency_pair,
        100
    )


# --------------------------------
# URGENCY PREMIUM
# --------------------------------
def get_urgency_premium(priority):

    premiums = {
        "standard": 0,
        "fast": 100,
        "instant": 300
    }

    return premiums.get(priority, 0)


# --------------------------------
# TOTAL PRICING
# --------------------------------
def calculate_pricing(
    amount,
    route_type,
    currency_pair="KES_KES",
    priority="standard"
):

    rail_cost = get_rail_cost(route_type)

    corridor_premium = get_corridor_premium(
        currency_pair
    )

    urgency_premium = get_urgency_premium(
        priority
    )

    total_fee = (
        rail_cost +
        corridor_premium +
        urgency_premium
    )

    net_amount = round(
        amount - total_fee,
        2
    )

    if net_amount <= 0:

        return {
            "error": "INVALID_NET_AMOUNT",
            "total_fee": total_fee,
            "net_amount": 0
        }

    return {
        "rail_cost": rail_cost,
        "corridor_premium": corridor_premium,
        "urgency_premium": urgency_premium,
        "total_fee": total_fee,
        "net_amount": net_amount
    }