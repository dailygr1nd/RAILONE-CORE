from psp_cross import get_fx_rate

SUPPORTED_CORRIDORS = {
    ("KES", "KES"),
    ("KES", "TZS"),
    ("KES", "UGX"),
    ("TZS", "KES"),
    ("TZS", "TZS"),
    ("TZS", "UGX"),
    ("UGX", "KES"),
    ("UGX", "TZS"),
    ("UGX", "UGX"),
    ("USD", "KES"),
    ("USD", "TZS"),
    ("USD", "UGX"),
    ("USD", "USD"),
}


def validate_corridor(src_currency, dst_currency):
    return (src_currency, dst_currency) in SUPPORTED_CORRIDORS


def quote_conversion(amount, src_currency, dst_currency):
    if not validate_corridor(src_currency, dst_currency):
        raise ValueError(f"Unsupported corridor: {src_currency} -> {dst_currency}")

    fx_rate = get_fx_rate(src_currency, dst_currency)
    converted_amount = round(amount * fx_rate, 2)

    return {
        "source_currency": src_currency,
        "destination_currency": dst_currency,
        "fx_rate": fx_rate,
        "converted_amount": converted_amount,
    }
