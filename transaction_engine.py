# ==============================
# transaction_engine.py
# ==============================

from datetime import datetime, UTC
from uuid import uuid4
import base64

from corridor_pricing_engine import calculate_pricing
from corridor_engine import build_corridor
from audit import log_event

from token_factory import TokenFactory
from execution_queue import enqueue_tx, store_tx

from fraud_engine import run_fraud_checks
from liquidity_engine import check_liquidity


# --------------------------------
# HELPERS
# --------------------------------
def extract_institution(account_id: str) -> str:
    return account_id.split("-")[0]


def generate_tx_id(sender_account: str) -> str:
    prefix = sender_account.split("-")[0]
    return f"{prefix}-RN-{uuid4().hex[:6].upper()}"


def encode_bytes(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def fail(tx: dict, reason: str):
    tx["status"] = "FAILED"
    tx["reason"] = reason

    store_tx(tx)
    log_event("TX_FAILED", tx)

    return tx


# --------------------------------
# MAIN ENTRY
# --------------------------------
def initiate_transaction(
    sender_account,
    receiver_account,
    amount,
    sender_currency,
    receiver_currency,
    webhook_url=None
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
        "webhook_url": webhook_url,
        "attempts": 0,
        "max_attempts": 3
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
    # INSTITUTION CONTEXT
    # --------------------------------
    sender_inst = extract_institution(sender_account)
    receiver_inst = extract_institution(receiver_account)

    # --------------------------------
    # TOKENS (JSON SAFE)
    # --------------------------------
    etk_s, sig_s, payload_s = TokenFactory.generate_etk_s(
        sender_account, amount, sender_inst
    )

    etk_r, sig_r, payload_r = TokenFactory.generate_etk_r(
        etk_s, receiver_account, receiver_inst
    )

    rtt, sig_rtt, payload_rtt = TokenFactory.generate_rtt(
        etk_s, etk_r, tx["tx_id"], sender_inst
    )

    tx.update({
        "etk_s": etk_s,
        "etk_r": etk_r,
        "rtt": rtt,
        "payload_s": payload_s,
        "payload_r": payload_r,
        "payload_rtt": payload_rtt,
        "signatures": {
            "etk_s": encode_bytes(sig_s),
            "etk_r": encode_bytes(sig_r),
            "rtt": encode_bytes(sig_rtt)
        }
    })

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

    log_event("ROUTE_SELECTED", tx)

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

    tx["net_amount"] = pricing["net_amount"]
    tx["fees"] = pricing["total_fee"]

    if tx["net_amount"] <= 0:
        return fail(tx, "INVALID_FEES")

    log_event("PRICING_COMPUTED", tx)

    # --------------------------------
    # FRAUD
    # --------------------------------
    ok, reason = run_fraud_checks(sender_account, amount)
    if not ok:
        return fail(tx, f"FRAUD_BLOCKED: {reason}")

    # --------------------------------
    # LIQUIDITY
    # --------------------------------
    ok, reason = ok, reason = check_liquidity(
    route=route,
    amount=tx["net_amount"]
)

    if not ok:
        return fail(tx, f"LIQUIDITY_ERROR: {reason}")

    # --------------------------------
    # ASYNC EXECUTION
    # --------------------------------
    tx["status"] = "PENDING"

    store_tx(tx)
    enqueue_tx(tx)

    log_event("TX_ENQUEUED", tx)

    return {
        "tx_id": tx["tx_id"],
        "status": "PENDING",
        "estimated_settlement": {
            "type": "RANGE",
            "min_minutes": 2,
            "max_minutes": 180
        }
    }