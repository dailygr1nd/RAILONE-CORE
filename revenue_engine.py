# ==============================
# revenue_engine.py (FINAL)
# ==============================

from railone_treasury import credit_treasury
from revenue_db import record_revenue


def extract_revenue(session, tx: dict):

    pricing = tx.get("pricing", {})

    base_fee = pricing.get("base_fee", 0)
    routing_fee = pricing.get("routing_fee", 0)
    fx_profit = pricing.get("fx_profit", 0)

    total = base_fee + routing_fee + fx_profit

    if total <= 0:
        return

    # 🔥 USE UTT (GLOBAL IDENTITY)
    utt = tx.get("utt", tx["tx_id"])

    record_revenue(
        tx_id=utt,
        amount=round(total, 2),
        currency=tx["currency_from"],
        route=tx["route_result"]["type"]
    )

    # 🔥 OPTIONAL: credit treasury (non-custodial simulation)
    try:
        credit_treasury(session, total, tx["currency_from"])
    except Exception:
        pass