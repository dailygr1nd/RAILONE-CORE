# ==============================
# transaction_engine.py (FINAL — PROTOCOL CORRECT)
# ==============================

from datetime import datetime, UTC

from audit import log_event
from execution_queue import enqueue_tx, store_tx

from balance_engine import lock_funds, release_funds
from smart_router import choose_best_route

from ledger.db import SessionLocal
from handshake import run_handshake

import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


# --------------------------------
# FAIL HANDLER
# --------------------------------
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
    sender_id: str,
    receiver_id: str,
    amount: float,
    sender_currency: str,
    receiver_currency: str,
    quote: dict | None = None
) -> dict:

    gross = float(amount)

    # --------------------------------
    # 🔐 HANDSHAKE
    # --------------------------------
    handshake = run_handshake(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=gross,
        currency=sender_currency
    )

    # --------------------------------
    # 🔒 IDEMPOTENCY (ETK-S)
    # --------------------------------
    existing = r.get(f"idem:{handshake['etk_s']}")

    if existing:
        return {
            "tx_id": existing,
            "status": "DUPLICATE_BLOCKED"
        }

    r.set(f"idem:{handshake['etk_s']}", handshake["tx_id"], ex=300)

    # --------------------------------
    # BUILD TX OBJECT
    # --------------------------------
    tx = {
        "tx_id": handshake["tx_id"],
        "rtt": handshake["rtt"],
        "rtt_signature": handshake["rtt_signature"],
        "etk_s": handshake["etk_s"],
        "etk_r": handshake["etk_r"],
        "ctx": handshake["ctx"],

        # UTT will be assigned AFTER execution
        "utt": None,

        "timestamp": datetime.now(UTC).isoformat(),

        "sender_account": sender_account,
        "receiver_account": receiver_account,

        "amount": gross,
        "gross_amount": gross,

        "currency_from": sender_currency,
        "currency_to": receiver_currency,

        "status": "INITIATED"
    }

    log_event("TX_INITIATED", tx)

    # --------------------------------
    # VALIDATION
    # --------------------------------
    if sender_account == receiver_account:
        return fail(tx, "SAME_ACCOUNT")

    if gross <= 0:
        return fail(tx, "INVALID_AMOUNT")

    session = SessionLocal()

    try:
        # --------------------------------
        # ROUTING
        # --------------------------------
        route = choose_best_route(tx, session)

        if not route:
            return fail(tx, "NO_ROUTE_AVAILABLE")

        tx["route_result"] = route

        # 🔐 bind route to RTT
        tx["route_hash"] = f"{route}-{tx['rtt']}"

        # --------------------------------
        # PRICING
        # --------------------------------
        if quote:
            tx["net_amount"] = float(quote.get("receive_amount", gross))
            tx["fee"] = float(quote.get("total_fee", 0))
            tx["profit"] = float(quote.get("profit", 0))
            tx["pricing"] = quote.get("pricing", {})
        else:
            tx["net_amount"] = gross
            tx["fee"] = 0.0
            tx["profit"] = 0.0
            tx["pricing"] = {}

        log_event("PRICING_COMPUTED", tx)

        # --------------------------------
        # LOCK FUNDS
        # --------------------------------
        total_debit = tx["gross_amount"] + tx["fee"]

        ok, reason = lock_funds(session, sender_account, total_debit)

        if not ok:
            return fail(tx, reason)

        session.commit()

    except Exception as e:
        session.rollback()
        return fail(tx, str(e))

    finally:
        session.close()

    # --------------------------------
    # ENQUEUE
    # --------------------------------
    tx["status"] = "PENDING"

    store_tx(tx)
    enqueue_tx(tx)

    log_event("TX_ENQUEUED", tx)

    return {
        "tx_id": tx["tx_id"],
        "status": "PENDING",
        "estimated_settlement": {
            "min_minutes": 2,
            "max_minutes": 180
        }
    }