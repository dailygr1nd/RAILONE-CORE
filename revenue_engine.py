# ==============================
# revenue_engine.py (PRODUCTION GRADE)
# ==============================

from railone_treasury import credit_treasury
from revenue_db import record_revenue


def extract_revenue(session, tx: dict):

    pricing = tx.get("pricing")

    if not pricing:
        print("⚠️ No pricing found — skipping revenue")
        return

    base_fee = pricing.get("base_fee", 0)
    routing_fee = pricing.get("routing_fee", 0)
    fx_profit = pricing.get("fx_profit", 0)

    total = base_fee + routing_fee + fx_profit

    if total <= 0:
        print("⚠️ Zero revenue transaction")
        return

    # --------------------------------
    # SAFE ROUTE EXTRACTION
    # --------------------------------
    route = tx.get("route_result", {})
    route_type = route.get("type", "UNKNOWN")

    # --------------------------------
    # USE UTT (FINAL ID)
    # --------------------------------
    tx_id = tx.get("utt") or tx.get("tx_id")

    try:
        record_revenue(
            tx_id=tx_id,
            amount=round(total, 2),
            currency=tx.get("currency_from", "UNKNOWN"),
            route=route_type
        )

        print(f"💰 Revenue recorded: {total} {tx.get('currency_from')}")

    except Exception as e:
        print("❌ Revenue DB error:", str(e))

    # --------------------------------
    # TREASURY CREDIT
    # --------------------------------
    try:
        credit_treasury(session, total, tx["currency_from"])
    except Exception:
        pass