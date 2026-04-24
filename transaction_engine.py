# ==============================
# transaction_engine.py (FINAL CLEAN)
# ==============================

from datetime import datetime, UTC
from uuid import uuid4

from audit import log_event
from execution_queue import enqueue_tx, store_tx

from balance_engine import reserve_funds, release_funds
from smart_router import choose_best_route

from fx_engine import convert
from corridor_fx_model import get_market_rate
from profit_engine import calculate_profit

from revenue_db import record_revenue

from ledger.db import SessionLocal


# --------------------------------
# HELPERS
# --------------------------------
def generate_tx_id(account):
    prefix = account.split("-")[0]
    return f"{prefix}-RN-{uuid4().hex[:6].upper()}"


def fail(tx, reason):
    tx["status"] = "FAILED"
    tx["reason"] = reason

    session = SessionLocal()
    try:
        release_funds(session, tx["sender_account"], tx["gross_amount"])
        session.commit()
    finally:
        session.close()

    store_tx(tx)
    log_event("TX_FAILED", tx)

    return tx


# --------------------------------
# MAIN
# --------------------------------
def initiate_transaction(
    sender_account,
    receiver_account,
    amount,
    sender_currency,
    receiver_currency,
    quote=None,
    webhook_url=None,
    idempotency_key=None
):

    tx = {
        "tx_id": generate_tx_id(sender_account),
        "timestamp": datetime.now(UTC).isoformat(),
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "amount": amount,
        "gross_amount": amount,
        "currency_from": sender_currency,
        "currency_to": receiver_currency,
        "status": "INITIATED",
        "webhook_url": webhook_url
    }

    log_event("TX_INITIATED", tx)

    if sender_account == receiver_account:
        return fail(tx, "SAME_ACCOUNT")

    if amount <= 0:
        return fail(tx, "INVALID_AMOUNT")

    session = SessionLocal()

    try:
        # -----------------------------
        # RESERVE FUNDS
        # -----------------------------
        ok, reason = reserve_funds(session, sender_account, amount)

        if not ok:
            return fail(tx, reason)

        session.commit()

        # -----------------------------
        # ROUTE
        # -----------------------------
        route = choose_best_route(tx, session)

        if not route:
            return fail(tx, "NO_ROUTE_AVAILABLE")

        tx["route_result"] = route

        # -----------------------------
        # LOCAL vs FX
        # -----------------------------
        if route["type"] == "LOCAL":

            net_amount = amount
            fx_rate = 1.0
            market_rate = 1.0
            profit = 0

        else:
            converted, fx_rate = convert(
                amount,
                sender_currency,
                receiver_currency,
                session
            )

            market_rate = get_market_rate(sender_currency, receiver_currency)

            net_amount = converted

            profit = calculate_profit({
                "gross_amount": amount,
                "net_amount": net_amount,
                "fx_rate": fx_rate,
                "market_rate": market_rate
            })["total_profit"]

        # -----------------------------
        # APPLY QUOTE (FINAL TRUTH)
        # -----------------------------
        if quote:
            net_amount = quote["receive_amount"]
            fee = quote["fee"]
            profit = quote["profit"]
        else:
            fee = 0

        tx["net_amount"] = net_amount
        tx["fx_rate"] = fx_rate
        tx["market_rate"] = market_rate
        tx["fee"] = fee
        tx["profit"] = profit

        log_event("PRICING_COMPUTED", tx)

    finally:
        session.close()

    # -----------------------------
    # ENQUEUE
    # -----------------------------
    tx["status"] = "PENDING"

    store_tx(tx)
    enqueue_tx(tx)

    log_event("TX_ENQUEUED", tx)

    # -----------------------------
    # RECORD REVENUE
    # -----------------------------
    record_revenue(
        tx_id=tx["tx_id"],
        amount=profit,
        currency=sender_currency,
        route=tx["route_result"]["type"]
    )

    return {
        "tx_id": tx["tx_id"],
        "status": "PENDING"
    }