# ==============================
# smart_router.py (PRO)
# ==============================

from fx_engine import convert
from settlement_capacity_signals import POOLS
from ledger.models import Account


# --------------------------------
# CONFIG
# --------------------------------
COST_WEIGHT = 2
SPEED_WEIGHT = 1

ROUTE_META = {
    "DIRECT": {
        "cost": 1,
        "speed": 3
    },
    "SMOVE": {
        "cost": 2,
        "speed": 1
    }
}


# --------------------------------
# LIQUIDITY CHECK
# --------------------------------
def has_liquidity(session, currency, amount):

    pool_id = POOLS.get(currency)

    if not pool_id:
        return False

    acc = session.query(Account).filter_by(id=pool_id).first()

    if not acc:
        return False

    return acc.mirrored_available_state >= amount


def route_local(tx, session):

    if tx["currency_from"] != tx["currency_to"]:
        return None

    amount = tx["gross_amount"]

    return {
        "type": "LOCAL",
        "net_amount": amount,
        "fx_rate": 1.0,
        "cost": 0,
        "speed": 5  # fastest
    }

# --------------------------------
# DIRECT ROUTE (BANK PATH)
# --------------------------------
def route_direct(tx, session):

    net, rate = convert(
        tx["gross_amount"],
        tx["currency_from"],
        tx["currency_to"],
        session
    )

    if net is None:
        return None

    if not has_liquidity(session, tx["currency_to"], net):
        return None

    return {
        "type": "DIRECT",
        "net_amount": net,
        "fx_rate": rate,
        "cost": ROUTE_META["DIRECT"]["cost"],
        "speed": ROUTE_META["DIRECT"]["speed"]
    }


# --------------------------------
# SMOVE ROUTE (PSP BRIDGE)
# --------------------------------
def route_smove(tx, session):

    net, rate = convert(
        tx["gross_amount"],
        tx["currency_from"],
        tx["currency_to"],
        session
    )

    if net is None:
        return None

    # OPTIONAL: slight penalty for SMOVE (latency/extra layer)
    net = round(net * 0.998, 2)

    if not has_liquidity(session, tx["currency_to"], net):
        return None

    return {
        "type": "SMOVE",
        "net_amount": net,
        "fx_rate": rate,
        "cost": ROUTE_META["SMOVE"]["cost"],
        "speed": ROUTE_META["SMOVE"]["speed"]
    }


# --------------------------------
# SCORING FUNCTION
# --------------------------------
def score_route(route):

    return (
        route["cost"] * COST_WEIGHT +
        route["speed"] * SPEED_WEIGHT
    )


# --------------------------------
# MAIN ROUTER
# --------------------------------
def choose_best_route(tx, session):

    candidates = []

    local = route_local(tx, session)
    if local:
     return local  # 🔥 always prefer local

    direct = route_direct(tx, session)
    if direct:
        candidates.append(direct)

    smove = route_smove(tx, session)
    if smove:
        candidates.append(smove)

    if not candidates:
        return None

    best = sorted(candidates, key=score_route)[0]

    return best

