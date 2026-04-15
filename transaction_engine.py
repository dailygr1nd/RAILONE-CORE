# transaction_engine.py

from datetime import datetime, UTC
from uuid import uuid4

from ledger import write_ledger_entry
from corridor_pricing_engine import calculate_pricing
from corridor_learning import learn_corridor

from user_accounts import (
    lock_funds,
    release_funds,
    settle_locked_funds,
    credit_account,
)

from audit import log_event
from corridor_engine import build_corridor


def generate_rtt():
    return f"RTT-{uuid4().hex[:12].upper()}"


def initiate_transaction(
    sender_account,
    receiver_account,
    amount,
    sender_currency,
    receiver_currency
):

    tx_id = generate_rtt()

    tx = {
        "tx_id": tx_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "amount": amount,
        "currency_from": sender_currency,
        "currency_to": receiver_currency,
        "status": "INITIATED",
    }

    log_event("TX_INITIATED", tx)

    # STEP 1: LOCK FUNDS
    if not lock_funds(sender_account, amount):
        tx["status"] = "FAILED"
        tx["reason"] = "INSUFFICIENT_FUNDS"
        log_event("TX_FAILED", tx)
        return tx

    tx["status"] = "FUNDS_LOCKED"
    log_event("FUNDS_LOCKED", tx)

    # STEP 2: CORRIDOR ENGINE
    route_result = build_corridor(
        sender_account,
        receiver_account,
        amount,
        sender_currency,
        receiver_currency
    )

    tx["route_result"] = route_result
    tx["status"] = "ROUTE_SELECTED"
    log_event("ROUTE_SELECTED", tx)

    # STEP 3: SIMULATED DISPATCH
    dispatch_success = True

    if not dispatch_success:
        release_funds(sender_account, amount)
        tx["status"] = "REVERSED"
        tx["reason"] = "DISPATCH_FAILED"
        log_event("TX_REVERSED", tx)
        return tx

    tx["status"] = "DISPATCHED"
    log_event("TX_DISPATCHED", tx)

    # STEP 4: SETTLEMENT
    best_route = route_result["best_route"]["rail"]

    pricing = calculate_pricing(
    amount,
    sender_currency,
    receiver_currency,
    best_route
)

    tx["pricing"] = pricing

    if not settle_locked_funds(sender_account, amount):
     tx["status"] = "FAILED"
     tx["reason"] = "SETTLEMENT_ERROR"
    log_event("TX_FAILED", tx)
    return tx

    if not credit_account(
    receiver_account,
    pricing["net_amount"]
):
     release_funds(sender_account, amount)

    tx["status"] = "REVERSED"
    tx["reason"] = "RECEIVER_CREDIT_FAILED"
    log_event("TX_REVERSED", tx)
    return tx

    tx["status"] = "SETTLED"

    write_ledger_entry(tx)

    log_event("TX_SETTLED", tx)

    return tx