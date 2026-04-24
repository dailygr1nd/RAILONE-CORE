# corridor_pricing_engine.py

BASE_SPREADS = {
    "TZS->KES": 0.012,
    "KES->TZS": 0.012,
    "TZS->UGX": 0.015,
    "UGX->TZS": 0.015,
    "KES->UGX": 0.011,
    "UGX->KES": 0.011,
    "USD->NGN": 0.018,
    "NGN->USD": 0.018,
    "USD->KES": 0.010,
    "USD->TZS": 0.010,
    "USD->UGX": 0.010,
    "DEFAULT": 0.02
}

BASE_FEES = {
    "BANK": 1500,
    "PSP": 500,
    "SMOVE": 750
}


def get_corridor_spread(from_ccy, to_ccy):
    key = f"{from_ccy}->{to_ccy}"
    return BASE_SPREADS.get(key, BASE_SPREADS["DEFAULT"])


def calculate_pricing(
    amount,
    from_ccy,
    to_ccy,
    route_type,
    fx_rate
):
    """
    NEW RULE:
    - FX is applied FIRST
    - Fees are applied on source amount
    - Final settlement uses converted_amount AFTER fees
    """

    spread = get_corridor_spread(from_ccy, to_ccy)

    if "BANK" in route_type:
        fee = BASE_FEES["BANK"]
    elif "PSP" in route_type:
        fee = BASE_FEES["PSP"]
    else:
        fee = BASE_FEES["SMOVE"]

    # Spread fee on source currency
    spread_fee = amount * spread

    total_fee = round(fee + spread_fee, 2)

    net_source_amount = round(amount - total_fee, 2)

    if net_source_amount <= 0:
        return {
            "error": "INVALID_NET_AMOUNT",
            "route_fee": fee,
            "spread": spread,
            "spread_fee": round(spread_fee, 2),
            "total_fee": total_fee,
            "net_amount": 0,
            "converted_amount": 0,
            "margin": round(spread_fee, 2)
        }

    # ✅ FX APPLIED ONLY ON FINAL NET AMOUNT
    converted_amount = round(net_source_amount / fx_rate, 2)

    return {
        "route_fee": fee,
        "spread": spread,
        "spread_fee": round(spread_fee, 2),
        "total_fee": total_fee,
        "net_amount": net_source_amount,
        "converted_amount": converted_amount,
        "fx_rate": fx_rate,
        "margin": round(spread_fee, 2)
    }