# ==============================
# retry_tx.py
# ==============================

from transaction_engine import initiate_transaction
from uuid import uuid4


def retry_transaction(tx):

    if tx["status"] != "FAILED":
        return {"error": "ONLY_FAILED_TX_CAN_BE_RETRIED"}

    return initiate_transaction(
        sender_account=tx["sender_account"],
        receiver_account=tx["receiver_account"],
        amount=tx["amount"],
        sender_currency=tx["currency_from"],
        receiver_currency=tx["currency_to"],
        idempotency_key=str(uuid4())
    )