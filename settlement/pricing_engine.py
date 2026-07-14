# ==============================
# pricing_engine.py (ADAPTIVE)
# ==============================

from settlement.liquidity_engine import get_liquidity_pressure


# --------------------------------
# BASE FEE
# --------------------------------
def compute_base_fee(amount):

    if amount <= 1000:
        return 10

    elif amount <= 10000:
        return amount * 0.005

    elif amount <= 100000:
        return amount * 0.003

    return min(amount * 0.002, 500)


# --------------------------------
# FX SPREAD
# --------------------------------
def compute_fx_spread(amount, is_cross_border):

    if not is_cross_border:
        return 0

    spread_rate = 0.015

    return amount * spread_rate


# --------------------------------
# ROUTING PREMIUM
# --------------------------------
def compute_routing_premium(route, amount):

    hops = len(route)

    if hops <= 1:
        return 0

    return min(amount * 0.001, 200)


# --------------------------------
# LIQUIDITY PREMIUM
# --------------------------------
def compute_liquidity_premium(
    amount,
    currency_pair,
    route_type
):

    pressure = get_liquidity_pressure(
        amount=amount,
        currency_pair=currency_pair,
        route_type=route_type
    )

    # low pressure
    if pressure < 0.3:
        return 0

    # moderate
    if pressure < 0.6:
        return amount * 0.0005

    # stressed
    return amount * 0.0015


# --------------------------------
# INSTITUTION TIER DISCOUNT
# --------------------------------
def compute_tier_discount(
    institution_tier,
    total_fee
):

    discounts = {
        "sandbox": 0,
        "starter": 0,
        "growth": 0.05,
        "enterprise": 0.15,
        "strategic": 0.25
    }

    pct = discounts.get(institution_tier, 0)

    return total_fee * pct


# --------------------------------
# TOTAL PRICING
# --------------------------------
def compute_total_pricing(
    amount,
    route,
    is_cross_border,
    currency_pair="KES_KES",
    route_type="domestic",
    institution_tier="starter"
):

    # --------------------------------
    # COMPONENTS
    # --------------------------------
    base_fee = compute_base_fee(amount)

    fx_profit = compute_fx_spread(
        amount,
        is_cross_border
    )

    routing_fee = compute_routing_premium(
        route,
        amount
    )

    liquidity_premium = compute_liquidity_premium(
        amount,
        currency_pair,
        route_type
    )

    subtotal = (
        base_fee +
        fx_profit +
        routing_fee +
        liquidity_premium
    )

    tier_discount = compute_tier_discount(
        institution_tier,
        subtotal
    )

    total = subtotal - tier_discount

    return {
        "base_fee": round(base_fee, 2),

        "fx_profit": round(fx_profit, 2),

        "routing_fee": round(routing_fee, 2),

        "liquidity_premium": round(liquidity_premium, 2),

        "tier_discount": round(tier_discount, 2),

        "total_revenue": round(total, 2)
    }