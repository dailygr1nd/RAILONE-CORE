# ==============================
# mainswitch.py (MULTI-TENANT)
# ==============================

from fastapi import FastAPI, Request, HTTPException
import hashlib
import hmac
import json

from transaction_engine import initiate_transaction
from execution_queue import get_tx
from idempotency_store import get_response, store_response

from auth_registry import get_institution_by_key
from rate_limiter import check_rate_limit

app = FastAPI()


# --------------------------------
# SIGNATURE VERIFY (PER-INSTITUTION)
# --------------------------------
def verify_signature(payload: dict, signature: str, secret: str):

    if not signature:
        raise HTTPException(status_code=401, detail="MISSING_SIGNATURE")

    payload_str = json.dumps(payload, sort_keys=True)

    computed = hmac.new(
        secret.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        raise HTTPException(status_code=401, detail="INVALID_SIGNATURE")


# --------------------------------
# TRANSFER
# --------------------------------
@app.post("/v1/transfers")
async def create_transfer(request: Request):

    body = await request.json()
    headers = request.headers

    api_key = headers.get("Authorization")
    signature = headers.get("X-RailOne-Signature")
    idem_key = headers.get("Idempotency-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="MISSING_API_KEY")

    if not idem_key:
        raise HTTPException(status_code=400, detail="MISSING_IDEMPOTENCY_KEY")

    # --------------------------------
    # AUTHENTICATION
    # --------------------------------
    inst, data = get_institution_by_key(api_key.replace("Bearer ", ""))

    if not inst:
        raise HTTPException(status_code=401, detail="INVALID_API_KEY")

    # --------------------------------
    # RATE LIMIT
    # --------------------------------
    allowed = check_rate_limit(
        api_key=inst,
        limit=data["rate_limit_per_min"]
    )

    if not allowed:
        raise HTTPException(status_code=429, detail="RATE_LIMIT_EXCEEDED")

    # --------------------------------
    # IDEMPOTENCY
    # --------------------------------
    cached = get_response(idem_key)
    if cached:
        return cached

    # --------------------------------
    # SIGNATURE VERIFY
    # --------------------------------
    verify_signature(body, signature, data["api_secret"])

    # --------------------------------
    # VALIDATION
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
            raise HTTPException(
                status_code=400,
                detail=f"MISSING_{field}"
            )

    # --------------------------------
    # EXECUTE
    # --------------------------------
    result = initiate_transaction(
        sender_account=body["sender_account"],
        receiver_account=body["receiver_account"],
        amount=body["amount"],
        sender_currency=body["currency_from"],
        receiver_currency=body["currency_to"],
        webhook_url=body.get("webhook_url")
    )

    store_response(idem_key, result)

    return result


# --------------------------------
# STATUS
# --------------------------------
@app.get("/v1/transactions/{tx_id}")
def get_transaction(tx_id: str):

    tx = get_tx(tx_id)

    if not tx:
        raise HTTPException(status_code=404, detail="TX_NOT_FOUND")

    return tx