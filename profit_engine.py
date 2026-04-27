# ==============================
# profit_engine.py (UPDATED)
# ==============================

def calculate_profit(tx):

    gross = tx["gross_amount"]
    net = tx["net_amount"]

    market_rate = tx.get("market_rate", 1)
    applied_rate = tx.get("fx_rate", 1)

    expected = gross * market_rate
    actual = net

    fx_profit = round(expected - actual, 2)

    fee_profit = tx.get("fee", 0)

    total_profit = round(fx_profit + fee_profit, 2)

    return {
        "fx_profit": fx_profit,
        "fee_profit": fee_profit,
        "total_profit": total_profit
    }