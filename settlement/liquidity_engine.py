# ==============================
# liquidity_engine.py (PROTOCOL SAFE)
# ==============================


# --------------------------------
# LIQUIDITY PRESSURE
# --------------------------------
def get_liquidity_pressure(**kwargs):
    """
    Flexible mock pressure engine.

    Accepts:
    - rail
    - currency
    - currency_pair
    - amount
    - route_type
    - etc.

    Prevents orchestration crashes
    while protocol evolves.
    """

    amount = kwargs.get("amount", 0)
    route_type = kwargs.get("route_type")

    try:

        # --------------------------------
        # MOCK PRESSURE LOGIC
        # --------------------------------
        if amount > 1_000_000:
            return 0.8

        if route_type == "cross_border":
            return 0.3

        return 0.1

    except Exception:
        return 0.5


# --------------------------------
# LIQUIDITY CHECK
# --------------------------------
def check_liquidity(**kwargs):
    """
    Flexible liquidity checker.

    Supports evolving routing APIs
    without breaking callers.
    """

    rail = kwargs.get("rail")
    currency = kwargs.get("currency")
    currency_pair = kwargs.get("currency_pair")
    amount = kwargs.get("amount", 0)
    route_type = kwargs.get("route_type")

    pressure = get_liquidity_pressure(**kwargs)

    # --------------------------------
    # MOCK LIMIT LOGIC
    # --------------------------------
    if pressure >= 0.95:

        return False, {
            "rail": rail,
            "currency": currency,
            "currency_pair": currency_pair,
            "amount": amount,
            "route_type": route_type,
            "pressure": pressure,
            "reason": "INSUFFICIENT_LIQUIDITY"
        }

    return True, {
        "rail": rail,
        "currency": currency,
        "currency_pair": currency_pair,
        "amount": amount,
        "route_type": route_type,
        "pressure": pressure,
        "status": "SUFFICIENT_LIQUIDITY"
    }


# --------------------------------
# RELEASE LIQUIDITY
# --------------------------------
def release_liquidity(currency_pair, amount):

    print(
        f"💧 Released liquidity → "
        f"{currency_pair} | amount={amount}"
    )

    return True