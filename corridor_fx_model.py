# corridor_fx_model.py

SUPPORTED_CURRENCIES = [
    "TZS", "KES", "UGX",
    "USD", "GBP", "EUR",
    "ZAR", "NGN", "EGP"
]

# --------------------------
# FX MATRIX (USD ANCHOR MODEL)
# --------------------------
FX_RATES = {
    ("USD", "KES"): 160,
    ("USD", "TZS"): 2600,
    ("USD", "UGX"): 3850,
    ("USD", "ZAR"): 18.5,
    ("USD", "NGN"): 1500,
    ("USD", "EGP"): 50,
    ("USD", "EUR"): 0.92,
    ("USD", "GBP"): 0.78,

    # reverse
    ("KES", "USD"): 1/160,
    ("TZS", "USD"): 1/2600,
    ("UGX", "USD"): 1/3850,
    ("ZAR", "USD"): 1/18.5,
    ("NGN", "USD"): 1/1500,
    ("EGP", "USD"): 1/50,
    ("EUR", "USD"): 1.09,
    ("GBP", "USD"): 1.28,
}

def validate_corridor(from_ccy, to_ccy):
    return from_ccy in SUPPORTED_CURRENCIES and to_ccy in SUPPORTED_CURRENCIES


def quote_conversion(amount, from_ccy, to_ccy):

    if from_ccy == to_ccy:
        return {
            "converted_amount": amount,
            "fx_rate": 1.0
        }

    rate = FX_RATES.get((from_ccy, to_ccy))

    # fallback via USD bridge
    if not rate:
        if (from_ccy, "USD") not in FX_RATES or ("USD", to_ccy) not in FX_RATES:
            raise Exception(f"Unsupported FX corridor: {from_ccy} -> {to_ccy}")

        usd_amount = amount * FX_RATES[(from_ccy, "USD")]
        rate = FX_RATES[("USD", to_ccy)]

        return {
            "converted_amount": round(usd_amount * rate, 2),
            "fx_rate": rate
        }

    return {
        "converted_amount": round(amount * rate, 2),
        "fx_rate": rate
    }