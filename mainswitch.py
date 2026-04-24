# ==============================
# mainswitch.py (CLEAN + SAFE)
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
    # VALIDATION
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
        "amount",
        "currency_from",
        "currency_to"
    ]

    for field in required:
        if field not in body:
            raise HTTPException(400, f"MISSING_{field}")

    # --------------------------------
    # EXECUTE
    # --------------------------------
    result = initiate_transaction(
        sender_account=body["sender_account"],
        receiver_account=body["receiver_account"],
        amount=body["amount"],
        sender_currency=body["currency_from"],
        receiver_currency=body["currency_to"],
        webhook_url=body.get("webhook_url"),
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