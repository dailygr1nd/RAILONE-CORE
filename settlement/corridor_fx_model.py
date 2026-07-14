# ==============================
# corridor_fx_model.py (MARKET DATA)
# ==============================

"""
This file provides RAW market FX rates.

IMPORTANT:
- No spreads here
- No business logic
- No fallbacks that hide errors
"""

FX_MARKET = {
    ("UGX", "KES"): 1 / 160,
    ("KES", "UGX"): 160,

    ("TZS", "KES"): 1 / 18,
    ("KES", "TZS"): 18,

    ("TZS", "UGX"): 1 / 60,
    ("UGX", "TZS"): 60,

    ("USD", "KES"): 130,
    ("KES", "USD"): 1 / 130,

    ("USD", "UGX"): 3800,
    ("UGX", "USD"): 1 / 3800,

    ("USD", "TZS"): 2500,
    ("TZS", "USD"): 1 / 2500,
}


def get_market_rate(from_ccy: str, to_ccy: str):

    if from_ccy == to_ccy:
        return 1.0

    rate = FX_MARKET.get((from_ccy, to_ccy))

    if rate is None:
        raise Exception(f"FX_RATE_NOT_FOUND: {from_ccy}->{to_ccy}")

    return rate