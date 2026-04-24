# ==============================
# profit_engine.py
# ==============================

def calculate_profit(tx):

    gross = tx["gross_amount"]
    net = tx["net_amount"]

    fx_rate = tx.get("fx_rate", 1)

    # what user SHOULD have gotten at market rate
    expected = gross * tx.get("market_rate", fx_rate)

    actual = net

    fx_profit = round(expected - actual, 2)

    fee_profit = tx.get("fees", 0)

    total_profit = round(fx_profit + fee_profit, 2)

    return {
        "fx_profit": fx_profit,
        "fee_profit": fee_profit,
        "total_profit": total_profit
    }