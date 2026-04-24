# ==============================# ==============================
# fx_engine.py (DYNAMIC)
# ==============================

from corridor_fx_model import get_market_rate
from liquidity_engine import get_liquidity_pressure

BASE_SPREAD_BPS = 100  # 1%


def get_dynamic_spread(from_ccy, to_ccy, amount, session):

    pressure = get_liquidity_pressure(session, to_ccy)

    spread = BASE_SPREAD_BPS

    # -----------------------------
    # Liquidity adjustment
    # -----------------------------
    if pressure == "LOW":
        spread += 50   # +0.5%

    elif pressure == "CRITICAL":
        spread += 150  # +1.5%

    # -----------------------------
    # Amount adjustment
    # -----------------------------
    if amount > 100_000:
        spread += 30

    if amount > 1_000_000:
        spread += 70

    return spread


def get_rate(from_ccy, to_ccy, amount, session):

    market = get_market_rate(from_ccy, to_ccy)

    spread_bps = get_dynamic_spread(from_ccy, to_ccy, amount, session)

    spread = market * (spread_bps / 10000)

    return market - spread


def convert(amount, from_ccy, to_ccy, session):

    rate = get_rate(from_ccy, to_ccy, amount, session)

    converted = amount * rate

    return round(converted, 2), rate