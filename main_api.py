# ==============================
# main_api.py (RAILONE API v1)
# ==============================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

from quote_engine import generate_quote
from transaction_engine import initiate_transaction
from execution_queue import get_tx


app = FastAPI(title="RailOne API", version="1.0")


# --------------------------------
# MODELS
# --------------------------------
class QuoteRequest(BaseModel):
    sender_id: str
    receiver_id: str
    amount: float
    currency_from: str
    currency_to: str


class TransactionRequest(BaseModel):
    sender_account: str
    receiver_account: str

    sender_id: str
    receiver_id: str

    amount: float
    currency_from: str
    currency_to: str

    quote: dict


# --------------------------------
# QUOTE
# --------------------------------
@app.post("/v1/quote")
def create_quote(req: QuoteRequest):

    quote = generate_quote(
        sender=req.sender_id,
        receiver=req.receiver_id,
        amount=req.amount,
        currency_from=req.currency_from,
        currency_to=req.currency_to
    )

    if "error" in quote:
        raise HTTPException(status_code=400, detail=quote["error"])

    return quote


# --------------------------------
# TRANSACTION
# --------------------------------
@app.post("/v1/transaction")
def create_transaction(req: TransactionRequest):

    try:
        result = initiate_transaction(
            sender_account=req.sender_account,
            receiver_account=req.receiver_account,

            sender_id=req.sender_id,
            receiver_id=req.receiver_id,

            amount=req.amount,
            sender_currency=req.currency_from,
            receiver_currency=req.currency_to,

            quote=req.quote,
            idempotency_key=str(uuid.uuid4())
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------
# STATUS
# --------------------------------
@app.get("/v1/transaction/{tx_id}")
def get_transaction(tx_id: str):

    tx = get_tx(tx_id)

    if not tx:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    return tx