# ==============================
# liquidity_engine.py (NON-CUSTODIAL, CORRIDOR-AWARE)
# ==============================

from liquidity_pools import POOLS


LOW_THRESHOLD = 0.2
CRITICAL_THRESHOLD = 0.1


# --------------------------------
# GET POOL BALANCE
# --------------------------------
def get_pool_balance(currency_pair):

    pool = POOLS.get(currency_pair)

    if not pool:
        return 0

    return pool["balance"]


# --------------------------------
# CHECK LIQUIDITY
# --------------------------------
def check_liquidity(route_type, currency_pair, amount):

    balance = get_pool_balance(currency_pair)

    if balance < amount:
        return False, "INSUFFICIENT_LIQUIDITY"

    return True, "OK"


# --------------------------------
# RESERVE LIQUIDITY
# --------------------------------
def reserve_liquidity(currency_pair, amount):

    pool = POOLS.get(currency_pair)

    if not pool or pool["balance"] < amount:
        raise Exception("LIQUIDITY_RESERVATION_FAILED")

    pool["balance"] -= amount


# --------------------------------
# RELEASE LIQUIDITY
# --------------------------------
def release_liquidity(currency_pair, amount):

    pool = POOLS.get(currency_pair)

    if pool:
        pool["balance"] += amount


# --------------------------------
# LIQUIDITY PRESSURE
# --------------------------------
def get_liquidity_pressure(currency_pair):

    balance = get_pool_balance(currency_pair)
    capacity = POOLS.get(currency_pair, {}).get("capacity", 5_000_000)

    ratio = balance / capacity if capacity else 0

    if ratio < CRITICAL_THRESHOLD:
        return "CRITICAL"
    elif ratio < LOW_THRESHOLD:
        return "LOW"

    return "NORMAL"