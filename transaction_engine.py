# ==============================
# transaction_engine.py (PROTOCOL LOCKED)
# ==============================

from datetime import datetime, UTC
import json
import hashlib
import time
import redis

from audit import log_event
from execution_queue import enqueue_tx, store_tx

from balance_engine import lock_funds, release_funds
from ledger.db import SessionLocal

from handshake import run_handshake
from token_factory import TokenFactory


r = redis.Redis(host="localhost", port=6379, decode_responses=True)


# --------------------------------
# 🔐 ROUTE HASH (DETERMINISTIC)
# --------------------------------
def compute_route_hash(route, rtt):
    route_str = json.dumps({
        "type": route.get("type"),
        "rail": route.get("rail"),
        "cost": round(route.get("cost", 0), 6)
    }, sort_keys=True)

    return hashlib.sha256(
        f"{route_str}|{rtt}".encode()
    ).hexdigest()


# --------------------------------
# 🔐 VERIFY QUOTE (STRICT)
# --------------------------------
def verify_quote(quote: dict):

    required = [
        "quote_id",
        "route",
        "pricing",
        "expires_at",
        "signature",
        "payload"
    ]

    for f in required:
        if f not in quote:
            return False, f"MISSING_{f}"

    # EXPIRY
    now = int(time.time())
    if quote["expires_at"] < now:
        return False, "QUOTE_EXPIRED"

    # SIGNATURE
    try:
        signature = bytes.fromhex(quote["signature"])
    except Exception:
        return False, "INVALID_SIGNATURE_FORMAT"

    if not TokenFactory.verify(
        quote["payload"],
        signature,
        "R1CORE"
    ):
        return False, "INVALID_QUOTE_SIGNATURE"

    return True, None


# --------------------------------
# ❌ FAIL HANDLER
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
# 🚀 MAIN ENTRY
# --------------------------------
def initiate_transaction(
    sender_account: str,
    receiver_account: str,
    sender_id: str,
    receiver_id: str,
    amount: float,
    sender_currency: str,
    receiver_currency: str,
    quote: dict,
    idempotency_key: str | None = None
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
    # 🔒 IDEMPOTENCY (EXPLICIT FIRST)
    # --------------------------------
    if idempotency_key:
        existing = r.get(f"idem:{idempotency_key}")
        if existing:
            return {
                "tx_id": existing,
                "status": "DUPLICATE_BLOCKED"
            }

    # --------------------------------
    # 🔒 IDEMPOTENCY (ETK-S FALLBACK)
    # --------------------------------
    etk_key = f"idem:{handshake['etk_s']}"

    if r.get(etk_key):
        return {
            "tx_id": r.get(etk_key),
            "status": "DUPLICATE_BLOCKED"
        }

    r.set(etk_key, handshake["tx_id"], ex=300)

    if idempotency_key:
        r.set(f"idem:{idempotency_key}", handshake["tx_id"], ex=300)

    # --------------------------------
    # BUILD TX
    # --------------------------------
    tx = {
        "tx_id": handshake["tx_id"],
        "etk_s": handshake["etk_s"],
        "etk_r": handshake["etk_r"],

        "rtt": None,
        "rtt_signature": None,
        "payload_rtt": None,
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
    # BASIC VALIDATION
    # --------------------------------
    if sender_account == receiver_account:
        return fail(tx, "SAME_ACCOUNT")

    if gross <= 0:
        return fail(tx, "INVALID_AMOUNT")

    # --------------------------------
    # 🔐 VERIFY QUOTE
    # --------------------------------
    valid, reason = verify_quote(quote)

    if not valid:
        return fail(tx, reason)

    quote_id = quote["quote_id"]

    # --------------------------------
    # 🔒 QUOTE REPLAY PROTECTION
    # --------------------------------
    if r.get(f"quote:{quote_id}"):
        return fail(tx, "QUOTE_ALREADY_USED")

    r.set(f"quote:{quote_id}", tx["tx_id"], ex=120)

    # --------------------------------
    # APPLY QUOTE
    # --------------------------------
    tx["quote_id"] = quote_id
    tx["pricing"] = quote["pricing"]
    tx["fee"] = quote["pricing"]["total_revenue"]
    tx["net_amount"] = quote["receive_amount"]
    tx["route_result"] = quote["route"]

    # --------------------------------
    # 🔐 RTT (FINAL BINDING)
    # --------------------------------
    rtt, sig_rtt, payload_rtt = TokenFactory.generate_rtt_with_quote(
        tx["etk_s"],
        tx["etk_r"],
        tx["tx_id"],
        tx["pricing"],
        quote_id,
        "R1CORE"
    )

    tx["rtt"] = rtt
    tx["rtt_signature"] = sig_rtt.hex()
    tx["payload_rtt"] = payload_rtt

    # --------------------------------
    # 🔒 LOCK FUNDS
    # --------------------------------
    session = SessionLocal()

    try:
        ok, reason = lock_funds(session, sender_account, gross)

        if not ok:
            return fail(tx, reason)

        session.commit()

    except Exception as e:
        session.rollback()
        return fail(tx, str(e))

    finally:
        session.close()

    # --------------------------------
    # 🔗 ROUTE BINDING
    # --------------------------------
    tx["route_hash"] = compute_route_hash(
        tx["route_result"],
        tx["rtt"]
    )

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
        "rtt": tx["rtt"],
        "estimated_settlement": {
            "min_minutes": 2,
            "max_minutes": 180
        }
    }