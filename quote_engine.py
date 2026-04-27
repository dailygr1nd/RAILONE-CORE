# ==============================
# quote_engine.py (MULTI-HOP + LIQUIDITY AWARE)
# ==============================

from fx_engine import get_fx_rate
from routing import build_route_with_constraints
from liquidity_engine import check_liquidity


def generate_quote(sender, receiver, amount, currency_from, currency_to):

    route = build_route_with_constraints(
        sender,
        receiver,
        amount,
        currency_from
    )

    if not route:
        return {"error": "NO_ROUTE_AVAILABLE"}

    current_amount = amount
    current_currency = currency_from

    total_fee = 0
    total_profit = 0

    for i in range(len(route)):

        rail = route[i]

        # -----------------------------
        # FX STEP
        # -----------------------------
        if i > 0:

            next_currency = currency_to if i == len(route) - 1 else "UGX"

            rate = get_fx_rate(current_currency, next_currency, current_amount)

            if not rate:
                return {"error": "FX_UNAVAILABLE"}

            converted = current_amount * rate

            # simulate spread
            market_rate = rate * 1.01

            fx_profit = (current_amount * market_rate) - converted

            total_profit += fx_profit

            current_amount = converted
            current_currency = next_currency

        # -----------------------------
        # LIQUIDITY CHECK
        # -----------------------------
        pair = f"{current_currency}_{current_currency}"

        has_liq, _ = check_liquidity(rail, pair, current_amount)

        if not has_liq:
            return {"error": "LIQUIDITY_FAIL"}

        # -----------------------------
        # FEES
        # -----------------------------
        fee = current_amount * 0.002
        total_fee += fee
        current_amount -= fee

    return {
        "route": route,
        "send_amount": amount,
        "receive_amount": round(current_amount, 2),
        "total_fee": round(total_fee, 2),
        "profit": round(total_profit + total_fee, 2)
    }