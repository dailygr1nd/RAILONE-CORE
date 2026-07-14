# ==============================
# fx_engine.py (ADAPTIVE FX)
# ==============================

from settlement.corridor_fx_model import get_market_rate

from settlement.liquidity_engine import (
    get_liquidity_pressure
)


BASE_SPREAD_BPS = 100  # 1%


# --------------------------------
# DYNAMIC SPREAD
# --------------------------------
def get_dynamic_spread(
    from_ccy,
    to_ccy,
    amount,
    session=None
):

    pressure = get_liquidity_pressure(
        currency=to_ccy,
        amount=amount,
        route_type="cross_border"
    )

    spread = BASE_SPREAD_BPS

    # --------------------------------
    # LIQUIDITY ADJUSTMENT
    # --------------------------------
    if pressure >= 0.8:

        spread += 150  # +1.5%

    elif pressure >= 0.5:

        spread += 50   # +0.5%

    # --------------------------------
    # AMOUNT ADJUSTMENT
    # --------------------------------
    if amount > 100_000:

        spread += 30

    if amount > 1_000_000:

        spread += 70

    return spread


# --------------------------------
# EFFECTIVE RATE
# --------------------------------
def get_rate(
    from_ccy,
    to_ccy,
    amount,
    session=None
):

    market = get_market_rate(
        from_ccy,
        to_ccy
    )

    spread_bps = get_dynamic_spread(
        from_ccy,
        to_ccy,
        amount,
        session
    )

    spread = market * (
        spread_bps / 10000
    )

    effective_rate = market - spread

    return round(effective_rate, 6)


# --------------------------------
# FX CONVERSION
# --------------------------------
def convert(
    amount,
    from_ccy,
    to_ccy,
    session=None
):

    # --------------------------------
    # SAME CURRENCY
    # --------------------------------
    if from_ccy == to_ccy:

        return round(amount, 2), 1

    # --------------------------------
    # FX CONVERSION
    # --------------------------------
    rate = get_rate(
        from_ccy,
        to_ccy,
        amount,
        session
    )

    converted = amount * rate

    return round(converted, 2), rate