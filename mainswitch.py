# mainswitch.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from zk_sd import onboard_user, USED_IDS
from corridor_fx_model import validate_corridor, quote_conversion
from transaction_engine import initiate_transaction
from audit import load_logs
from key_manager import KeyManager


app = FastAPI(title="RailOne API", version="1.0.0")


# ---------------------------
# MODELS
# ---------------------------

class TransferRequest(BaseModel):
    sender_account: str
    receiver_account: str
    amount: float = Field(..., gt=0)
    sender_currency: str
    receiver_currency: str


class QuoteRequest(BaseModel):
    amount: float
    sender_currency: str
    receiver_currency: str


class OnboardRequest(BaseModel):
    name: str
    nid: str
    role: str = "user"


# ---------------------------
# HEALTH
# ---------------------------

@app.get("/ping")
def ping():
    return {"status": "alive", "protocol": "RailOne"}


# ---------------------------
# ONBOARD
# ---------------------------

@app.post("/v1/onboard")
def onboard(req: OnboardRequest):

    if req.nid in USED_IDS:
        raise HTTPException(400, "Already onboarded")

    user = onboard_user(req.name, req.nid, req.role)

    if not user:
        raise HTTPException(422, "Verification failed")

    return user


# ---------------------------
# QUOTE
# ---------------------------

@app.post("/v1/quote")
def quote(req: QuoteRequest):

    if not validate_corridor(req.sender_currency, req.receiver_currency):
        raise HTTPException(422, "Unsupported corridor")

    q = quote_conversion(req.amount, req.sender_currency, req.receiver_currency)

    return {
        "amount": req.amount,
        "fx_rate": q["fx_rate"],
        "converted": q["converted_amount"]
    }


# ---------------------------
# TRANSFER
# ---------------------------

@app.post("/v1/transfers")
def transfer(req: TransferRequest):

    tx = initiate_transaction(
        sender_account=req.sender_account,
        receiver_account=req.receiver_account,
        amount=req.amount,
        sender_currency=req.sender_currency,
        receiver_currency=req.receiver_currency
    )

    if tx["status"] != "SETTLED":
        raise HTTPException(422, tx.get("reason"))

    return {
        "utt": tx["utt"],
        "status": tx["status"],
        "route": tx.get("route_result", {}).get("best_route", {})
    }


# ---------------------------
# STATUS
# ---------------------------

@app.get("/v1/transfers/{utt}")
def status(utt: str):

    logs = load_logs()

    entries = [
        e for e in logs
        if e.get("payload", {}).get("utt") == utt
    ]

    if not entries:
        raise HTTPException(404, "Not found")

    return {
        "utt": utt,
        "events": entries
    }
# mainswitch.py

from ledger.db import SessionLocal
from ledger.models import Transaction


@app.get("/v1/transactions/{tx_id}")
def get_tx_status(tx_id: str):
    session = SessionLocal()

    tx = session.query(Transaction).filter_by(id=tx_id).first()

    if not tx:
        return {"error": "NOT_FOUND"}

    return {
        "tx_id": tx.id,
        "status": tx.status,
        "amount": tx.amount,
        "currency": tx.currency
    }

@app.post("/v1/institutions/onboard")
def onboard_institution(payload: dict):

    institution_id = payload.get("institution_id")

    if not institution_id:
        return {"error": "missing institution_id"}

    public_key = KeyManager.onboard_institution(institution_id)

    return {
        "status": "ONBOARDED",
        "institution_id": institution_id
    }