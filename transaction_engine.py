# ==============================
# transaction_engine.py
# ==============================

from datetime import datetime, UTC
from uuid import uuid4
import random

from state_machine import TransactionContext, TransactionState

from ledger.db import SessionLocal
from ledger.models import Transaction as DBTransaction
from ledger.ledger_service import apply_double_entry

from corridor_pricing_engine import calculate_pricing
from corridor_learning import learn_corridor
from corridor_engine import build_corridor

from user_accounts import (
    lock_funds,
    release_funds,
    settle_locked_funds,
    credit_account,
)

from audit import log_event
from token_factory import TokenFactory


# --------------------------------
# UTIL
# --------------------------------
def generate_tx_id(sender_account: str) -> str:
    institution_id = sender_account.split("-")[0]
    suffix = uuid4().hex[:6].upper()
    return f"{institution_id}-RN-{suffix}"


# --------------------------------
# FAIL HANDLER
# --------------------------------
def handle_failure(tx_ctx, db_tx, session, reason, sender_account=None, amount=None):
    if sender_account and amount:
        release_funds(sender_account, amount)

    tx_ctx.transition(TransactionState.FAILED)
    db_tx.status = tx_ctx.state.value
    db_tx.updated_at = datetime.now(UTC)

    db_tx.metadata = str({**tx_ctx.metadata, "reason": reason})
    session.commit()

    log_event("TX_FAILED", {**tx_ctx.to_dict(), "reason": reason})

    return tx_ctx.to_dict()


# --------------------------------
# MAIN ENGINE
# --------------------------------
def initiate_transaction(
    sender_account,
    receiver_account,
    amount,
    sender_currency,
    receiver_currency,
    idempotency_key=None,
):
    session = SessionLocal()

    # --------------------------------
    # IDEMPOTENCY
    # --------------------------------
    if idempotency_key:
        existing = session.query(DBTransaction).filter_by(
            idempotency_key=idempotency_key
        ).first()

        if existing:
            return {"tx_id": existing.id, "status": existing.status}

    tx_id = generate_tx_id(sender_account)

    # --------------------------------
    # CONTEXT
    # --------------------------------
    tx_ctx = TransactionContext(
        tx_id=tx_id,
        amount=amount,
        currency=sender_currency,
        sender_id=sender_account,
        receiver_id=receiver_account,
    )

    # --------------------------------
    # DB RECORD
    # --------------------------------
    db_tx = DBTransaction(
        id=tx_id,
        sender_id=sender_account,
        receiver_id=receiver_account,
        amount=amount,
        currency=sender_currency,
        status=tx_ctx.state.value,
        idempotency_key=idempotency_key,
    )
    session.add(db_tx)
    session.commit()

    log_event("TX_INITIATED", tx_ctx.to_dict())

    # --------------------------------
    # SAME ACCOUNT BLOCK
    # --------------------------------
    if sender_account == receiver_account:
        return handle_failure(tx_ctx, db_tx, session, "SAME_ACCOUNT")

    # --------------------------------
    # LOCK FUNDS
    # --------------------------------
    if not lock_funds(sender_account, amount):
        return handle_failure(tx_ctx, db_tx, session, "INSUFFICIENT_FUNDS")

    tx_ctx.transition(TransactionState.SENDER_LOCKED)
    db_tx.status = tx_ctx.state.value
    session.commit()

    # --------------------------------
    # ROUTING
    # --------------------------------
    tx_ctx.transition(TransactionState.ROUTING)
    db_tx.status = tx_ctx.state.value
    session.commit()

    route_result = build_corridor(
        sender_account,
        receiver_account,
        amount,
        sender_currency,
        receiver_currency
    )

    best_route = route_result.get("best_route", {})
    tx_ctx.metadata["route"] = best_route

    # --------------------------------
    # RECEIVER CONFIRMATION (SIMULATED)
    # --------------------------------
    tx_ctx.transition(TransactionState.RECEIVER_CONFIRMED)
    db_tx.status = tx_ctx.state.value
    session.commit()

    # --------------------------------
    # HANDSHAKE (ETK + RTT)
    # --------------------------------
    etk_s = TokenFactory.generate_etk_s(sender_account, amount)
    etk_r = TokenFactory.generate_etk_r(etk_s, receiver_account)
    rtt = TokenFactory.generate_rtt(etk_s, etk_r, tx_context=tx_id)

    tx_ctx.metadata.update({
        "etk_s": etk_s,
        "etk_r": etk_r,
        "rtt": rtt
    })

    tx_ctx.transition(TransactionState.HANDSHAKE_VERIFIED)
    db_tx.status = tx_ctx.state.value
    session.commit()

    # --------------------------------
    # PRICING
    # --------------------------------
    pricing = calculate_pricing(
        amount=amount,
        from_ccy=sender_currency,
        to_ccy=receiver_currency,
        route_type=best_route.get("type", "SMOVE")
    )

    tx_ctx.metadata["pricing"] = pricing

    net_amount = pricing.get("net_amount", 0)

    if net_amount <= 0:
        return handle_failure(tx_ctx, db_tx, session, "INVALID_PRICING", sender_account, amount)

    # --------------------------------
    # EXECUTION
    # --------------------------------
    tx_ctx.transition(TransactionState.PROCESSED)
    db_tx.status = tx_ctx.state.value
    session.commit()

    success_probability = best_route.get("success_probability", 0.95)
    rail_success = random.random() < success_probability

    if not rail_success:
        return handle_failure(tx_ctx, db_tx, session, "RAIL_FAILURE", sender_account, amount)

    # --------------------------------
    # SETTLEMENT
    # --------------------------------
    settle_locked_funds(sender_account, amount)

    if not credit_account(receiver_account, net_amount):
        return handle_failure(tx_ctx, db_tx, session, "CREDIT_FAILED", sender_account, amount)

    # --------------------------------
    # LEDGER (SOURCE OF TRUTH)
    # --------------------------------
    apply_double_entry(
        session,
        tx_id,
        sender_account,
        receiver_account,
        amount,
        sender_currency
    )

    tx_ctx.transition(TransactionState.SETTLED)
    db_tx.status = tx_ctx.state.value
    session.commit()

    log_event("TX_SETTLED", tx_ctx.to_dict())

    learn_corridor(
        from_ccy=sender_currency,
        to_ccy=receiver_currency,
        route_type=best_route.get("type", "SMOVE"),
        success=True,
        latency_ms=random.randint(300, 1200)
    )

    return tx_ctx.to_dict()