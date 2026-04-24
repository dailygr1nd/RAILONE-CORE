# ==============================
# quote_engine.py
# ==============================

from fx_engine import convert
from corridor_fx_model import get_market_rate
from smart_router import choose_best_route
from ledger.db import SessionLocal


def generate_quote(
    sender_account,
    receiver_account,
    amount,
    sender_currency,
    receiver_currency
):

    session = SessionLocal()

    try:
        tx = {
            "sender_account": sender_account,
            "receiver_account": receiver_account,
            "gross_amount": amount,
            "currency_from": sender_currency,
            "currency_to": receiver_currency
        }

        route = choose_best_route(tx, session)

        if not route:
            return {
                "error": "NO_ROUTE_AVAILABLE"
            }

        # -----------------------------
        # LOCAL TRANSFER
        # -----------------------------
        if route["type"] == "LOCAL":

            fee = round(amount * 0.005, 2)  # 0.5% simple fee
            receive = round(amount - fee, 2)

            return {
                "route": "LOCAL",
                "fx_rate": 1.0,
                "market_rate": 1.0,
                "fee": fee,
                "send_amount": amount,
                "receive_amount": receive,
                "profit": fee
            }

        # -----------------------------
        # FX TRANSFER
        # -----------------------------
        converted, rate = convert(
            amount,
            sender_currency,
            receiver_currency,
            session
        )

        market_rate = get_market_rate(sender_currency, receiver_currency)

        fx_profit = round((amount * market_rate) - converted, 2)

        fee = round(amount * 0.003, 2)  # small fee

        receive = round(converted - fee, 2)

        return {
            "route": route["type"],
            "fx_rate": rate,
            "market_rate": market_rate,
            "fee": fee,
            "send_amount": amount,
            "receive_amount": receive,
            "profit": fx_profit + fee
        }

    finally:
        session.close()