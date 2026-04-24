# corridor_fx_model.py

FX_RATES = {
    # Format: "FROM->TO": rate (FROM per 1 TO)

    "UGX->KES": 160,
    "KES->UGX": 1 / 160,

    "TZS->KES": 18,
    "KES->TZS": 1 / 18,

    "TZS->UGX": 60,
    "UGX->TZS": 1 / 60,

    "USD->KES": 130,
    "KES->USD": 1 / 130,

    "USD->UGX": 3800,
    "UGX->USD": 1 / 3800,

    "USD->TZS": 2500,
    "TZS->USD": 1 / 2500,
}


def get_fx_rate(from_ccy, to_ccy):
    key = f"{from_ccy}->{to_ccy}"

    if key in FX_RATES:
        return FX_RATES[key]

    # fallback (avoid crash, but visible)
    return 1


def quote_conversion(amount, from_ccy, to_ccy):
    """
    Deterministic FX conversion

    RULE:
    fx_rate = source per 1 target
    converted_amount = amount / fx_rate
    """

    fx_rate = get_fx_rate(from_ccy, to_ccy)

    converted_amount = round(amount / fx_rate, 2)

    return {
        "fx_rate": fx_rate,
        "converted_amount": converted_amount
    }