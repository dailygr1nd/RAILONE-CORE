# ==============================
# mainswitch.py (RailOne API)
# ==============================

from fastapi import FastAPI, HTTPException

from execution_queue import get_tx

app = FastAPI(title="RailOne Switch API")


# --------------------------------
# TRANSFER (already exists probably)
# --------------------------------
from transaction_engine import initiate_transaction

@app.post("/v1/transfers")
def create_transfer(payload: dict):
    return initiate_transaction(
        sender_account=payload["sender_account"],
        receiver_account=payload["receiver_account"],
        amount=payload["amount"],
        sender_currency=payload["sender_currency"],
        receiver_currency=payload["receiver_currency"]
    )


# --------------------------------
# TX STATUS
# --------------------------------
@app.get("/v1/tx/{tx_id}")
def get_transaction(tx_id: str):

    tx = get_tx(tx_id)

    if not tx:
        raise HTTPException(status_code=404, detail="TX_NOT_FOUND")

    return {
        "tx_id": tx["tx_id"],
        "status": tx["status"],
        "amount": tx["amount"],
        "currency": tx["currency_from"],
        "route": tx.get("route_result"),
        "timestamps": {
            "created": tx.get("timestamp")
        }
    }


# --------------------------------
# INVESTIGATE BY UTT
# --------------------------------
@app.get("/v1/investigate/utt/{utt}")
def investigate_utt(utt: str):

    # naive search (later optimize)
    from execution_queue import redis_client, TX_STORE
    import json

    all_txs = redis_client.hgetall(TX_STORE)

    for tx_json in all_txs.values():
        tx = json.loads(tx_json)
        if tx.get("utt") == utt:
            return tx

    raise HTTPException(status_code=404, detail="UTT_NOT_FOUND")


# --------------------------------
# INVESTIGATE BY RTT
# --------------------------------
@app.get("/v1/investigate/rtt/{rtt}")
def investigate_rtt(rtt: str):

    from execution_queue import redis_client, TX_STORE
    import json

    all_txs = redis_client.hgetall(TX_STORE)

    for tx_json in all_txs.values():
        tx = json.loads(tx_json)
        if tx.get("rtt") == rtt:
            return tx

    raise HTTPException(status_code=404, detail="RTT_NOT_FOUND")