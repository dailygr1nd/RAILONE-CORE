from datetime import datetime, UTC
from uuid import uuid4

from corridor_pricing_engine import calculate_pricing
from corridor_learning import learn_corridor
from audit import log_event
from corridor_engine import build_corridor
from token_factory import TokenFactory

from ledger.db import SessionLocal

from liquidity_engine import check_liquidity
from fraud_engine import run_fraud_checks
from rail_executor import execute_on_rail
from ledger.ledger_service import log_transaction  # rename if needed

# --------------------------------
def generate_tx_id(sender_account: str) -> str:
    prefix = sender_account.split("-")[0]
    return f"{prefix}-RN-{uuid4().hex[:6].upper()}"


# --------------------------------
def fail(tx, reason):
    tx["status"] = "FAILED"
    tx["reason"] = reason
    log_event("TX_FAILED", tx)
    return tx


# --------------------------------
def initiate_transaction(
    sender_account,
    receiver_account,
    amount,
    sender_currency,
    receiver_currency
):
    tx = {
        "tx_id": generate_tx_id(sender_account),
        "timestamp": datetime.now(UTC).isoformat(),
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "amount": amount,
        "gross_amount": amount,
        "net_amount": None,
        "fees": 0,
        "currency_from": sender_currency,
        "currency_to": receiver_currency,
        "status": "INITIATED",
        "route_result": None,
        "reason": None,
    }

    log_event("TX_INITIATED", tx)

    # --------------------------------
    # VALIDATION
    # --------------------------------
    if sender_account == receiver_account:
        return fail(tx, "SAME_ACCOUNT")

    if amount <= 0:
        return fail(tx, "INVALID_AMOUNT")

    # --------------------------------
    # FRAUD CHECK (MUST BE EARLY)
    # --------------------------------
    ok, reason = run_fraud_checks(sender_account, amount)

    if not ok:
        return fail(tx, f"FRAUD_BLOCKED: {reason}")

    # --------------------------------
    # TOKENS
    # --------------------------------
    tx["etk_s"] = TokenFactory.generate_etk_s(sender_account, amount)
    tx["etk_r"] = TokenFactory.generate_etk_r(tx["etk_s"], receiver_account)
    tx["rtt"] = TokenFactory.generate_rtt(
        tx["etk_s"], tx["etk_r"], tx["tx_id"]
    )

    log_event("TOKENS_GENERATED", tx)

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

    tx["route_result"] = route
    best = route.get("best_route", {})

    tx["status"] = "ROUTE_SELECTED"
    log_event("ROUTE_SELECTED", tx)


    # DEBUG / INTELLIGENCE LOG
    log_event("ROUTE_DECISION", {
    "tx_id": tx["tx_id"],
    "candidates": route["candidates"],
    "selected": best
})

    # --------------------------------
    # PRICING
    # --------------------------------
    pricing = calculate_pricing(
    amount=amount,
    from_ccy=sender_currency,
    to_ccy=receiver_currency,
    route_type=best.get("type", "SMOVE"),
    fx_rate=best.get("fx_rate", 1.0)  # 🔥 FIX
)

    tx["net_amount"] = pricing["net_amount"]
    tx["fees"] = pricing["total_fee"]

    log_event("PRICING_COMPUTED", tx)

    if tx["net_amount"] <= 0:
        return fail(tx, "INVALID_FEES")

    # --------------------------------
    # LIQUIDITY CHECK (CRITICAL)
    # --------------------------------
    ok, reason = check_liquidity(
        route_type=best.get("rail", "SMOVE"),
        currency=sender_currency,
        amount=tx["net_amount"]
    )

    if not ok:
        return fail(tx, f"LIQUIDITY_ERROR: {reason}")

    # --------------------------------
    # DISPATCH
    # --------------------------------
    tx["status"] = "DISPATCHED"
    log_event("TX_DISPATCHED", tx)

    # --------------------------------
# EXECUTION (NON-CUSTODIAL)
# --------------------------------
    execution_result = execute_on_rail(best, tx)

    if not execution_result.get("success"):
        return fail(tx, execution_result.get("reason"))

    tx["execution"] = execution_result

    # --------------------------------
# LEDGER (SHADOW RECORD)
# --------------------------------
    log_transaction(tx)

  

    # --------------------------------
    # FINALIZATION
    # --------------------------------
    tx["utt"] = TokenFactory.generate_utt(
        best.get("rail", "R1CORE")
    )

    tx["status"] = "SETTLED"
    log_event("TX_SETTLED", tx)

    # --------------------------------
    # LEARNING
    # --------------------------------
    learn_corridor(
        from_ccy=sender_currency,
        to_ccy=receiver_currency,
        route_type=best.get("type", "SMOVE"),
        success=True,
        latency_ms=500
    )

    return tx