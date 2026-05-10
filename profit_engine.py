# ==============================
# profit_engine.py (INFRA MODEL)
# ==============================

def calculate_profit(tx):

    gross_amount = float(tx.get("gross_amount", 0))
    fee_profit = float(tx.get("fee", 0))

    market_rate = float(tx.get("market_rate", 1))
    applied_rate = float(tx.get("fx_rate", 1))

    # --------------------------------
    # FX SPREAD PROFIT
    # --------------------------------
    fx_profit = 0

    if market_rate > 0 and applied_rate > 0:

        rate_delta = applied_rate - market_rate

        fx_profit = round(
            gross_amount * rate_delta,
            2
        )

    # --------------------------------
    # TOTAL
    # --------------------------------
    total_profit = round(
        fee_profit + fx_profit,
        2
    )

    return {
        "fee_profit": round(fee_profit, 2),
        "fx_profit": round(fx_profit, 2),
        "total_profit": round(total_profit, 2),
        "market_rate": market_rate,
        "applied_rate": applied_rate
    }