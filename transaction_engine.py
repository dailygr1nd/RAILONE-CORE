from datetime import datetime, UTC
from uuid import uuid4

from user_accounts import (
    lock_funds,
    release_funds,
    settle_locked_funds,
    credit_account,
)

from routing import select_best_route
from audit import log_event


def generate_rtt() -> str:
    return f"RTT-{uuid4().hex[:12].upper()}"


def initiate_transaction(
    sender_account: str,
    receiver_account: str,
    amount: float,
    corridor: str = "LOCAL",
):
    tx_id = generate_rtt()

    tx = {
        "tx_id": tx_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "amount": amount,
        "corridor": corridor,
        "status": "INITIATED",
    }

    log_event("TX_INITIATED", tx)

    # STEP 1: LOCK FUNDS
    locked = lock_funds(sender_account, amount)

    if not locked:
        tx["status"] = "FAILED"
        tx["reason"] = "INSUFFICIENT_FUNDS"

        log_event("TX_FAILED", tx)
        return tx

    tx["status"] = "FUNDS_LOCKED"
    log_event("FUNDS_LOCKED", tx)

    # STEP 2: ROUTE SELECTION
    route = select_best_route(amount, corridor)

    if not route:
        release_funds(sender_account, amount)

        tx["status"] = "REVERSED"
        tx["reason"] = "NO_ROUTE_AVAILABLE"

        log_event("TX_REVERSED", tx)
        return tx

    tx["route"] = route
    tx["status"] = "ROUTE_SELECTED"
    log_event("ROUTE_SELECTED", tx)

    # STEP 3: DISPATCH SIMULATION
    dispatch_success = True

    if not dispatch_success:
        release_funds(sender_account, amount)

        tx["status"] = "REVERSED"
        tx["reason"] = "DISPATCH_FAILED"

        log_event("TX_REVERSED", tx)
        return tx

    tx["status"] = "DISPATCHED"
    log_event("TX_DISPATCHED", tx)

    # STEP 4: FINAL SETTLEMENT
    settled = settle_locked_funds(sender_account, amount)

    if not settled:
        tx["status"] = "FAILED"
        tx["reason"] = "SETTLEMENT_ERROR"

        log_event("TX_FAILED", tx)
        return tx

    credited = credit_account(receiver_account, amount)

    if not credited:
        release_funds(sender_account, amount)

        tx["status"] = "REVERSED"
        tx["reason"] = "RECEIVER_CREDIT_FAILED"

        log_event("TX_REVERSED", tx)
        return tx

    tx["status"] = "SETTLED"
    log_event("TX_SETTLED", tx)

    return tx