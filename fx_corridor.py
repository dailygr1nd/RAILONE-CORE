# fx_corridor.py

SUPPORTED_CURRENCIES = [
    "TZS", "KES", "UGX",
    "USD", "GBP", "EUR",
    "ZAR", "NGN", "EGP"
]

# --------------------------
# FX MATRIX (SIMPLIFIED REALISTIC RATES)
# base = USD anchor
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

    # cross African corridors via USD
    ("KES", "TZS"): 2600/160,
    ("TZS", "KES"): 160/2600,
    ("KES", "UGX"): 3850/160,
    ("UGX", "KES"): 160/3850,
    ("TZS", "UGX"): 3850/2600,
    ("UGX", "TZS"): 2600/3850,
}


# --------------------------
# VALIDATION
# --------------------------
def validate_corridor(from_ccy, to_ccy):
    return from_ccy in SUPPORTED_CURRENCIES and to_ccy in SUPPORTED_CURRENCIES


# --------------------------
# FX QUOTE ENGINE
# --------------------------
def quote_conversion(amount, from_ccy, to_ccy):
    if from_ccy == to_ccy:
        return {
            "converted_amount": amount,
            "fx_rate": 1.0
        }

    # direct match
    rate = FX_RATES.get((from_ccy, to_ccy))

    # fallback via USD bridge
    if not rate:
        try:
            usd_amount = amount / FX_RATES[(from_ccy, "USD")]
            rate = FX_RATES[("USD", to_ccy)]
            return {
                "converted_amount": round(usd_amount * rate, 2),
                "fx_rate": rate
            }
        except:
            raise Exception("Unsupported FX corridor")

    return {
        "converted_amount": round(amount * rate, 2),
        "fx_rate": rate
    }