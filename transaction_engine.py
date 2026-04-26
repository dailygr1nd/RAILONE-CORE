# ==============================
# transaction_engine.py (STABLE FINAL)
# ==============================

from datetime import datetime, UTC
from uuid import uuid4

from audit import log_event
from execution_queue import enqueue_tx, store_tx

from balance_engine import lock_funds, release_funds
from smart_router import choose_best_route

from fx_engine import convert
from corridor_fx_model import get_market_rate
from profit_engine import calculate_profit

from revenue_db import record_revenue
from ledger.db import SessionLocal


# --------------------------------
# HELPERS
# --------------------------------
def generate_tx_id(account: str) -> str:
    prefix = account.split("-")[0]
    return f"{prefix}-RN-{uuid4().hex[:6].upper()}"


def fail(tx: dict, reason: str) -> dict:
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
# MAIN ENTRY
# --------------------------------
def initiate_transaction(
    sender_account: str,
    receiver_account: str,
    amount: float,
    sender_currency: str,
    receiver_currency: str,
    quote: dict | None = None,
    webhook_url: str | None = None,
    idempotency_key: str | None = None
) -> dict:

    gross = float(amount)
    fee = 0.0

    tx = {
        "tx_id": generate_tx_id(sender_account),
        "timestamp": datetime.now(UTC).isoformat(),
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "amount": gross,
        "gross_amount": gross,
        "currency_from": sender_currency,
        "currency_to": receiver_currency,
        "status": "INITIATED",
        "webhook_url": webhook_url,
        "idempotency_key": idempotency_key
    }

    log_event("TX_INITIATED", tx)

    # -----------------------------
    # VALIDATION
    # -----------------------------
    if sender_account == receiver_account:
        return fail(tx, "SAME_ACCOUNT")

    if gross <= 0:
        return fail(tx, "INVALID_AMOUNT")

    session = SessionLocal()

    try:
        # -----------------------------
        # ROUTING
        # -----------------------------
        route = choose_best_route(tx, session)

        if not route:
            return fail(tx, "NO_ROUTE_AVAILABLE")

        tx["route_result"] = route

        # -----------------------------
        # PRICING
        # -----------------------------
        if quote:
            net_amount = float(quote.get("receive_amount", gross))
            fee = float(quote.get("fee", 0))
            profit = float(quote.get("profit", 0))
            fx_rate = quote.get("fx_rate", 1.0)
            market_rate = quote.get("market_rate", 1.0)

        else:
            if route["type"] == "LOCAL":
                net_amount = gross
                fx_rate = 1.0
                market_rate = 1.0
                profit = 0.0

            else:
                converted, fx_rate = convert(
                    gross,
                    sender_currency,
                    receiver_currency,
                    session
                )

                market_rate = get_market_rate(
                    sender_currency,
                    receiver_currency
                )

                net_amount = float(converted)

                profit = calculate_profit({
                    "gross_amount": gross,
                    "net_amount": net_amount,
                    "fx_rate": fx_rate,
                    "market_rate": market_rate
                })["total_profit"]

        tx["net_amount"] = net_amount
        tx["fx_rate"] = fx_rate
        tx["market_rate"] = market_rate
        tx["fee"] = fee
        tx["profit"] = profit

        log_event("PRICING_COMPUTED", tx)

        # -----------------------------
        # LOCK FUNDS
        # -----------------------------
        total_debit = gross + fee

        ok, reason = lock_funds(session, sender_account, total_debit)

        if not ok:
            return fail(tx, reason)

        session.commit()

    except Exception as e:
        session.rollback()
        return fail(tx, str(e))

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
    # REVENUE TRACKING
    # -----------------------------
    try:
        record_revenue(
            tx_id=tx["tx_id"],
            amount=tx["profit"],
            currency=sender_currency,
            route=tx["route_result"]["type"]
        )
    except Exception:
        pass

    return {
        "tx_id": tx["tx_id"],
        "status": "PENDING",
        "estimated_settlement": {
            "min_minutes": 2,
            "max_minutes": 180
        }
    }