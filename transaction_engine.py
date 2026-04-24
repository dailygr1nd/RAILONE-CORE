# ==============================
# transaction_engine.py
# ASYNC + IDEMPOTENCY + AUTH + RATE LIMIT
# ==============================

from datetime import datetime, UTC
from uuid import uuid4

from corridor_pricing_engine import calculate_pricing
from corridor_engine import build_corridor
from corridor_learning import learn_corridor

from audit import log_event
from token_factory import TokenFactory

from ledger.db import SessionLocal
from ledger.models import Transaction

from liquidity_engine import check_liquidity
from fraud_engine import run_fraud_checks

from state_machine import TransactionContext, TransactionState

from execution_queue import enqueue_transaction
from auth_engine import authenticate_client
from rate_limiter import check_rate_limit


# --------------------------------
# TX ID
# --------------------------------
def generate_tx_id(sender_account: str) -> str:
    prefix = sender_account.split("-")[0]
    return f"{prefix}-RN-{uuid4().hex[:6].upper()}"


# --------------------------------
# FAILURE
# --------------------------------
def fail(ctx, reason):
    ctx.state = TransactionState.FAILED
    ctx.metadata["reason"] = reason
    log_event("TX_FAILED", ctx.to_dict())
    return ctx.to_dict()


# --------------------------------
# MAIN ENTRY
# --------------------------------
def initiate_transaction(payload: dict):

    # --------------------------------
    # CLIENT AUTH
    # --------------------------------
    client_id = payload.get("client_id")
    api_key = payload.get("api_key")

    if not authenticate_client(client_id, api_key):
        return {"error": "UNAUTHORIZED"}

    # --------------------------------
    # RATE LIMIT
    # --------------------------------
    if not check_rate_limit(client_id):
        return {"error": "RATE_LIMIT_EXCEEDED"}

    sender_account = payload["sender_account"]
    receiver_account = payload["receiver_account"]
    amount = payload["amount"]
    sender_currency = payload["sender_currency"]
    receiver_currency = payload["receiver_currency"]
    idempotency_key = payload.get("idempotency_key")

    # --------------------------------
    # DB SESSION
    # --------------------------------
    session = SessionLocal()

    try:
        # --------------------------------
        # IDEMPOTENCY CHECK
        # --------------------------------
        if idempotency_key:
            existing = session.query(Transaction).filter_by(
                idempotency_key=idempotency_key
            ).first()

            if existing:
                return {
                    "tx_id": existing.id,
                    "status": existing.status
                }

        # --------------------------------
        # CONTEXT
        # --------------------------------
        ctx = TransactionContext(
            tx_id=generate_tx_id(sender_account),
            amount=amount,
            currency=sender_currency,
            sender_id=sender_account,
            receiver_id=receiver_account
        )

        ctx.metadata["client_id"] = client_id

        log_event("TX_INITIATED", ctx.to_dict())

        # --------------------------------
        # VALIDATION
        # --------------------------------
        if sender_account == receiver_account:
            return fail(ctx, "SAME_ACCOUNT")

        if amount <= 0:
            return fail(ctx, "INVALID_AMOUNT")

        # --------------------------------
        # TOKENS
        # --------------------------------
        etk_s = TokenFactory.generate_etk_s(sender_account, amount)
        etk_r = TokenFactory.generate_etk_r(etk_s, receiver_account)
        rtt = TokenFactory.generate_rtt(etk_s, etk_r, ctx.tx_id)

        ctx.metadata.update({
            "etk_s": etk_s,
            "etk_r": etk_r,
            "rtt": rtt
        })

        # --------------------------------
        # ROUTING
        # --------------------------------
        route = build_corridor(
            sender_account,
            receiver_account,
            amount,
            sender_currency,
            receiver_currency
        )

        best = route["best_route"]

        ctx.metadata["route"] = route

        # --------------------------------
        # PRICING
        # --------------------------------
        pricing = calculate_pricing(
            amount=amount,
            from_ccy=sender_currency,
            to_ccy=receiver_currency,
            route_type=best.get("type", "SMOVE"),
            fx_rate=best.get("fx_rate", 1.0)
        )

        net_amount = pricing["net_amount"]

        ctx.metadata["pricing"] = pricing
        ctx.metadata["net_amount"] = net_amount

        if net_amount <= 0:
            return fail(ctx, "INVALID_FEES")

        # --------------------------------
        # VALIDATION (LIQUIDITY + FRAUD)
        # --------------------------------
        ok, reason = check_liquidity(
            best.get("rail", "SMOVE"),
            sender_currency,
            net_amount
        )

        if not ok:
            return fail(ctx, f"LIQUIDITY_ERROR: {reason}")

        ok, reason = run_fraud_checks(sender_account, amount)

        if not ok:
            return fail(ctx, f"FRAUD_BLOCKED: {reason}")

        # --------------------------------
        # SAVE TRANSACTION (PENDING)
        # --------------------------------
        db_tx = Transaction(
            id=ctx.tx_id,
            sender_id=sender_account,
            receiver_id=receiver_account,
            amount=amount,
            currency=sender_currency,
            status="PENDING",
            idempotency_key=idempotency_key
        )

        session.add(db_tx)
        session.commit()

        # --------------------------------
        # ENQUEUE FOR ASYNC EXECUTION
        # --------------------------------
        enqueue_transaction({
            "tx": ctx.to_dict(),
            "route": route
        })

        # --------------------------------
        # RETURN IMMEDIATELY
        # --------------------------------
        return {
            "tx_id": ctx.tx_id,
            "status": "PENDING",
            "estimated_settlement": {
                "type": "RANGE",
                "min_minutes": 2,
                "max_minutes": 180
            }
        }

    except Exception as e:
        session.rollback()
        return {"error": str(e)}

    finally:
        session.close()