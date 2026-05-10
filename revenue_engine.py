# ==============================
# revenue_engine.py (PROTOCOL ALIGNED)
# ==============================

from revenue_db import record_revenue


def extract_revenue(session, tx):

    try:

        pricing = tx.get("pricing", {})

        gross_amount = float(tx.get("gross_amount", 0))

        fee_amount = float(
            pricing.get("fee_amount", tx.get("fee", 0))
        )

        fx_profit = float(
            pricing.get("fx_profit", 0)
        )

        currency = tx.get("currency_from")

        route_result = tx.get("route_result", {})

        route = route_result.get(
            "rail",
            route_result.get("type", "UNKNOWN")
        )

        total_revenue = fee_amount + fx_profit

        # --------------------------------
        # STORE REVENUE
        # --------------------------------
        record_revenue(
            tx_id=tx["tx_id"],
            gross_amount=gross_amount,
            fee_amount=fee_amount,
            fx_profit=fx_profit,
            currency=currency,
            route=route
        )

        print(
            f"💰 Revenue captured → "
            f"{total_revenue} {currency}"
        )

        return {
            "gross_amount": gross_amount,
            "fee_amount": fee_amount,
            "fx_profit": fx_profit,
            "total_revenue": total_revenue,
            "currency": currency,
            "route": route
        }

    except Exception as e:

        print(f"❌ Revenue DB error: {str(e)}")

        return None