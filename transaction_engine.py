# transaction_engine.py

from datetime import datetime, UTC
from uuid import uuid4
import random

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

    # --------------------------------
    # STEP 1: INITIATE
    # --------------------------------
    log_event("TX_INITIATED", tx)

    # --------------------------------
    # STEP 2: LOCK FUNDS
    # --------------------------------
    if not lock_funds(sender_account, amount):
        tx["status"] = "FAILED"
        tx["reason"] = "INSUFFICIENT_FUNDS"
        log_event("TX_FAILED", tx)
        return tx

    tx["status"] = "FUNDS_LOCKED"
    log_event("FUNDS_LOCKED", tx)

    # --------------------------------
    # STEP 3: BUILD CORRIDOR
    # --------------------------------
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

    # --------------------------------
    # STEP 4: PRICING
    # --------------------------------
    best_route = route_result.get("best_route", {})

    pricing = calculate_pricing(
    amount=amount,
    from_ccy=sender_currency,
    to_ccy=receiver_currency,
    route_type=best_route.get("type", "SMOVE")
)

    # --------------------------------
    # STEP 5: DISPATCH
    # --------------------------------
    tx["status"] = "DISPATCHED"
    log_event("TX_DISPATCHED", tx)

    # --------------------------------
    # STEP 6: SIMULATED RAIL SUCCESS
    # --------------------------------
    best_route = route_result.get("best_route", {})
    success_probability = best_route.get(
        "success_probability",
        0.99
    )

    rail_success = random.random() < success_probability

    # --------------------------------
    # SUCCESS PATH
    # --------------------------------
    if rail_success:
        # permanently debit locked funds
        settle_locked_funds(
            sender_account,
            amount
        )

        # credit receiver
        credit_success = credit_account(
            receiver_account,
            pricing["net_amount"]
        )

        if not credit_success:
            release_funds(sender_account, amount)

            tx["status"] = "REVERSED"
            tx["reason"] = "RECEIVER_CREDIT_FAILED"

            log_event("TX_REVERSED", tx)
            return tx

        tx["status"] = "SETTLED"

        write_ledger_entry({
            "tx_id": tx["tx_id"],
            "timestamp": tx["timestamp"],
            "sender_account": sender_account,
            "receiver_account": receiver_account,
            "gross_amount": amount,
            "net_amount": pricing["net_amount"],
            "fees": pricing["total_fee"],
            "currency_from": sender_currency,
            "currency_to": receiver_currency,
            "status": "SETTLED",
            "route": best_route.get("rail"),
        })

        log_event("TX_SETTLED", tx)

        # learning feedback
        learn_corridor(
            route_result,
            success=True
        )

        return tx

    # --------------------------------
    # FAILURE PATH
    # --------------------------------
    release_funds(sender_account, amount)

    tx["status"] = "FAILED"
    tx["reason"] = "RAIL_TIMEOUT"

    log_event("TX_FAILED", tx)

    learn_corridor(
        route_result,
        success=False
    )

    return tx