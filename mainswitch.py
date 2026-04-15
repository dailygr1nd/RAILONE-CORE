# mainswitch.py  —  RailOne Sandbox API
# Endpoints:
#   GET  /ping                   health check
#   POST /onboard                onboard a user, get RailOneID + accounts
#   POST /quote                  get FX quote + fee estimate for a corridor
#   POST /transact               full ETK handshake + settlement dispatch
#   GET  /status/{utt}           lookup transaction state from audit log
#   GET  /rails                  live rail health scores
#   GET  /compliance/alerts      flush pending compliance alerts

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from zk_sd import onboard_user, USED_IDS
from corridor_fx_model import validate_corridor, quote_conversion
from transaction_engine import TransactionEngine
from routing_brain import compute_rail_health
from compliance import get_compliance_alerts
from audit import load_logs
from telemetry import ROUTE_TELEMETRY

app = FastAPI(
    title="RailOne Prototype API",
    description="Non-custodial transaction verification & routing — East Africa sandbox",
    version="0.4.0",
)

_engine = TransactionEngine()

# ──────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ──────────────────────────────────────────

class OnboardRequest(BaseModel):
    name: str
    nid: str
    role: str = "user"


class QuoteRequest(BaseModel):
    amount: float = Field(..., gt=0)
    sender_currency: str
    receiver_currency: str


class TransactRequest(BaseModel):
    sender_id: str
    receiver_id: str
    amount: float = Field(..., gt=0)
    debit_account_id: str
    credit_account_id: str
    sender_currency: str
    receiver_currency: str


# ──────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────

@app.get("/ping")
def ping():
    """Health check — confirms API is alive."""
    return {"status": "alive", "protocol": "RailOne v0.4.0"}


@app.post("/onboard")
def onboard_user_api(req: OnboardRequest):
    """
    Onboard a new user. Verifies identity against registry,
    generates RailOneID, ZK proof, KYC attestation, and accounts.
    """
    if req.nid in USED_IDS:
        raise HTTPException(status_code=400, detail="ID already onboarded this session")

    user_data = onboard_user(name=req.name, nid=req.nid, role=req.role)

    if not user_data:
        raise HTTPException(status_code=422, detail="Identity verification failed")

    return {
        "username": user_data["username"],
        "railone_id": user_data["railone_id"],
        "kyc_level": user_data["attestation"]["kyc_level"],
        "zk_proof": user_data["zk_proof"],
        "accounts": user_data["accounts"],
        "attestation": {
            "issuer": user_data["attestation"]["issuer"],
            "verified": user_data["attestation"]["verified"],
            "timestamp": user_data["attestation"]["timestamp"],
        },
    }


@app.post("/quote")
def get_quote(req: QuoteRequest):
    """
    Returns FX rate, converted amount, and fee estimate for a corridor.
    No funds move. Safe to call repeatedly before /transact.
    """
    if not validate_corridor(req.sender_currency, req.receiver_currency):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported corridor: {req.sender_currency} → {req.receiver_currency}",
        )

    quote = quote_conversion(req.amount, req.sender_currency, req.receiver_currency)

    # Simple fee model: 0.5% capped at 2000 KES-equivalent
    fee_pct = 0.005
    fee = round(req.amount * fee_pct, 2)
    net_receiver = round(quote["converted_amount"] - (fee * quote["fx_rate"]), 2)

    return {
        "sender_sends": req.amount,
        "sender_currency": req.sender_currency,
        "fx_rate": quote["fx_rate"],
        "receiver_gets": net_receiver,
        "receiver_currency": req.receiver_currency,
        "fee_sender_currency": fee,
        "corridor": f"{req.sender_currency}→{req.receiver_currency}",
    }


@app.post("/transact")
def create_transaction(req: TransactRequest):
    """
    Full RailOne transaction flow:
    ETK-S generation → compliance → corridor validation →
    FX quote → debit lock → routing brain + failover → credit → audit.
    Returns UTT for tracking.
    """
    success, message, utt = _engine.create_transaction(
        sender_id=req.sender_id,
        receiver_id=req.receiver_id,
        amount=req.amount,
        debit_account_id=req.debit_account_id,
        credit_account_id=req.credit_account_id,
        sender_currency=req.sender_currency,
        receiver_currency=req.receiver_currency,
    )

    if not success:
        raise HTTPException(
            status_code=422,
            detail={"message": message, "utt": utt},
        )

    return {
        "success": True,
        "utt": utt,
        "message": message,
        "sender_currency": req.sender_currency,
        "receiver_currency": req.receiver_currency,
        "amount": req.amount,
    }


@app.get("/status/{utt}")
def get_transaction_status(utt: str):
    """
    Looks up all audit log entries for a given UTT.
    Returns the full state trail — useful for sandbox debugging.
    """
    logs = load_logs()
    entries = [
        entry for entry in logs
        if entry.get("payload", {}).get("utt") == utt
    ]

    if not entries:
        raise HTTPException(status_code=404, detail=f"No records found for UTT: {utt}")

    # The last FINAL_STATE entry is ground truth
    final = next(
        (e for e in reversed(entries) if e["event"] == "FINAL_STATE"),
        None,
    )

    return {
        "utt": utt,
        "current_status": final["payload"]["status"] if final else "IN_PROGRESS",
        "trail": [
            {"event": e["event"], "timestamp": e["timestamp"], "payload": e["payload"]}
            for e in entries
        ],
    }


@app.get("/rails")
def get_rail_health():
    """
    Returns live brain-computed health scores for all active rails.
    Combines static telemetry baseline with live routing_metrics drift.
    """
    rails = list(ROUTE_TELEMETRY.keys())
    health = {}

    for rail in rails:
        score = compute_rail_health(rail)
        t = ROUTE_TELEMETRY[rail]
        health[rail] = {
            "health_score": score,
            "success_rate": t["success_rate"],
            "avg_latency_ms": t["avg_latency_ms"],
            "uptime": t["uptime"],
            "reversal_rate": t["reversal_rate"],
        }

    return {
        "rails": health,
        "ranked": sorted(health.keys(), key=lambda r: health[r]["health_score"], reverse=True),
    }


@app.get("/compliance/alerts")
def get_alerts():
    """
    Flushes and returns any pending compliance alerts
    (high-risk corridors, EDD triggers, PEP flags).
    """
    alerts = get_compliance_alerts()
    return {"count": len(alerts), "alerts": alerts}