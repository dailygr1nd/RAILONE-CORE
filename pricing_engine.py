# ==============================
# pricing_engine.py
# ==============================

def compute_base_fee(amount, currency):
    """
    Tiered pricing (realistic emerging market structure)
    """

    if amount <= 1000:
        return 10
    elif amount <= 10000:
        return amount * 0.005  # 0.5%
    elif amount <= 100000:
        return amount * 0.003  # 0.3%
    else:
        return min(amount * 0.002, 500)  # cap

def compute_fx_spread(amount):
    """
    FX spread (core revenue)
    """
    spread_rate = 0.015  # 1.5%
    return amount * spread_rate

def compute_routing_premium(route, amount):
    """
    Charge only when value is delivered
    """

    # simple heuristic
    hops = len(route)

    if hops <= 1:
        return 0

    # multi-hop intelligence fee
    return min(amount * 0.001, 200)  # 0.1% capped


def compute_total_pricing(amount, route, is_cross_border):

    base_fee = compute_base_fee(amount, None)

    fx_profit = compute_fx_spread(amount) if is_cross_border else 0

    routing_fee = compute_routing_premium(route, amount)

    total = base_fee + fx_profit + routing_fee

    return {
        "base_fee": round(base_fee, 2),
        "fx_profit": round(fx_profit, 2),
        "routing_fee": round(routing_fee, 2),
        "total_revenue": round(total, 2)
    }