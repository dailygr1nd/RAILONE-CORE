# ==============================
# mainswitch.py (PROTOCOL ALIGNED)
# ==============================

from fastapi import FastAPI, Request, HTTPException
import json

from transaction_engine import initiate_transaction
from execution_queue import get_tx

from idempotency_store import check_idempotency, store_idempotency

from auth_registry import get_institution_by_key, get_rate_limit
from auth_engine import verify_request
from rate_limiter import check_rate_limit

from request_logger import log_request
from iso_adapter import build_pacs008

app = FastAPI()

from ledger.db import SessionLocal

from settlement_reference_engine import (
    settlement_reference_snapshot,
    get_settlement_reference_pressure,
    get_corridor_state
)

from railone_settlement_reference import (
    settlement_reference_snapshot as railone_snapshot
)

# --------------------------------
# UTIL
# --------------------------------
def extract_api_key(header: str):
    if not header:
        return None
    return header.replace("Bearer ", "").strip()


# --------------------------------
# TRANSFER
# --------------------------------
@app.post("/v1/transfers")
async def create_transfer(request: Request):

    body = await request.json()
    headers = request.headers

    api_key = extract_api_key(headers.get("Authorization"))
    signature = headers.get("X-RailOne-Signature")
    timestamp = headers.get("X-RailOne-Timestamp")
    idem_key = headers.get("Idempotency-Key")

    # --------------------------------
    # BASIC VALIDATION
    # --------------------------------
    if not api_key:
        raise HTTPException(401, "MISSING_API_KEY")

    if not signature or not timestamp:
        raise HTTPException(401, "MISSING_SIGNATURE_OR_TIMESTAMP")

    if not idem_key:
        raise HTTPException(400, "MISSING_IDEMPOTENCY_KEY")

    # --------------------------------
    # IDEMPOTENCY
    # --------------------------------
    cached = check_idempotency(idem_key)
    if cached:
        return cached

    # --------------------------------
    # AUTH
    # --------------------------------
    inst, data = get_institution_by_key(api_key)

    if not inst:
        raise HTTPException(401, "INVALID_API_KEY")

    payload_str = json.dumps(body, sort_keys=True)

    ok, reason = verify_request(
        api_key=api_key,
        signature=signature,
        payload=payload_str,
        timestamp=timestamp
    )

    if not ok:
        raise HTTPException(401, reason)

    # --------------------------------
    # RATE LIMIT
    # --------------------------------
    limit = get_rate_limit(api_key)

    if not check_rate_limit(api_key, limit):
        raise HTTPException(429, "RATE_LIMIT_EXCEEDED")

    # --------------------------------
    # LOG REQUEST
    # --------------------------------
    log_request(api_key, "/v1/transfers", body)

    # --------------------------------
    # REQUIRED FIELDS
    # --------------------------------
    required = [
        "sender_account",
        "receiver_account",
        "sender_id",
        "receiver_id",
        "amount",
        "currency_from",
        "currency_to",
        "quote"
    ]

    for field in required:
        if field not in body:
            raise HTTPException(400, f"MISSING_{field}")

    # --------------------------------
    # EXECUTION (ENGINE OWNS VALIDATION)
    # --------------------------------
    result = initiate_transaction(
        sender_account=body["sender_account"],
        receiver_account=body["receiver_account"],
        sender_id=body["sender_id"],
        receiver_id=body["receiver_id"],
        amount=body["amount"],
        sender_currency=body["currency_from"],
        receiver_currency=body["currency_to"],
        quote=body["quote"],
        idempotency_key=idem_key
    )

    # --------------------------------
    # STORE IDEMPOTENCY
    # --------------------------------
    store_idempotency(idem_key, result)

    return result


# --------------------------------
# STATUS
# --------------------------------
@app.get("/v1/transactions/{tx_id}")
def get_transaction(tx_id: str):

    tx = get_tx(tx_id)

    if not tx:
        raise HTTPException(404, "TX_NOT_FOUND")

    return tx


# --------------------------------
# ISO EXPORT
# --------------------------------
@app.get("/v1/iso/pacs008/{tx_id}")
def get_iso(tx_id: str):

    tx = get_tx(tx_id)

    if not tx:
        raise HTTPException(404, "TX_NOT_FOUND")

    return {"pacs008": build_pacs008(tx)}


# --------------------------------
# DASHBOARD METRICS (unchanged)
# --------------------------------
from revenue_db import get_total_revenue
import sqlite3


@app.get("/v1/dashboard/summary")
def dashboard_summary():
    return {"total_revenue": get_total_revenue()}


@app.get("/v1/dashboard/by-route")
def revenue_by_route():

    conn = sqlite3.connect("railone_revenue.db")
    c = conn.cursor()

    c.execute("""
    SELECT route, SUM(amount)
    FROM revenue
    GROUP BY route
    """)

    rows = c.fetchall()
    conn.close()

    return [{"route": r[0], "revenue": r[1]} for r in rows]


@app.get("/v1/dashboard/daily")
def revenue_daily():

    conn = sqlite3.connect("railone_revenue.db")
    c = conn.cursor()

    c.execute("""
    SELECT DATE(timestamp), SUM(amount)
    FROM revenue
    GROUP BY DATE(timestamp)
    ORDER BY DATE(timestamp)
    """)

    rows = c.fetchall()
    conn.close()

    return [{"date": r[0], "revenue": r[1]} for r in rows]


@app.get("/v1/dashboard/metrics")
def dashboard_metrics():

    conn = sqlite3.connect("railone_revenue.db")
    c = conn.cursor()

    c.execute("SELECT SUM(amount) FROM revenue")
    total = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*) FROM revenue")
    tx_count = c.fetchone()[0]

    avg = total / tx_count if tx_count > 0 else 0

    conn.close()

    return {
        "total_revenue": total,
        "transactions": tx_count,
        "avg_profit": round(avg, 2)
    }
# --------------------------------
# settlement_reference SNAPSHOT
# --------------------------------
@app.get("/v1/settlement_reference/snapshot")
def get_settlement_reference_snapshot():

    session = SessionLocal()

    try:

        network = settlement_reference_snapshot(session)

        railone = railone_snapshot(session)

        return {
            "network_liquidity": network,
            "railone_reserves": railone
        }

    finally:
        session.close()

# --------------------------------
# settlement_reference PRESSURE
# --------------------------------
@app.get("/v1/settlement_reference/pressure/{currency}")
def settlement_reference_pressure(currency: str):

    session = SessionLocal()

    try:

        result = get_settlement_reference_pressure(
            session,
            currency.upper()
        )

        return result

    finally:
        session.close()

# --------------------------------
# CORRIDOR PRESSURE
# --------------------------------
@app.get("/v1/corridors/pressure/{pair}")
def corridor_pressure(pair: str):

    session = SessionLocal()

    try:

        result = get_corridor_state(
            session,
            pair.upper()
        )

        return result

    finally:
        session.close()

# --------------------------------
# NETWORK LIQUIDITY
# --------------------------------
@app.get("/v1/network/liquidity")
def network_liquidity():

    session = SessionLocal()

    try:

        currencies = [
            "KES",
            "UGX",
            "TZS",
            "USD"
        ]

        data = {}

        for currency in currencies:

            data[currency] = get_settlement_reference_pressure(
                session,
                currency
            )

        return {
            "network": data
        }

    finally:
        session.close()                        