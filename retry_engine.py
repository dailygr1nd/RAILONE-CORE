# ==============================
# retry_engine.py (FIXED)
# ==============================

from uuid import uuid4
from routing import get_best_rail
from transaction_engine import initiate_transaction


def retry_transaction(tx):

    if tx["status"] != "FAILED":
        return {"error": "ONLY_FAILED_TX_CAN_BE_RETRIED"}

    # --------------------------------
    # RECOMPUTE BEST ROUTE
    # --------------------------------
    new_route = get_best_rail(
        candidate_rails=["PSP_KE", "PSP_UG", "BANK_TZ", "SMOVE"],
        amount=tx["amount"],
        currency=tx["currency_from"],
        cross_border=True
    )

    print(f"[RETRY] New route selected: {new_route}")

    # --------------------------------
    # RE-INITIATE TRANSACTION
    # --------------------------------
    return initiate_transaction(
        sender_account=tx["sender_account"],
        receiver_account=tx["receiver_account"],
        amount=tx["amount"],
        sender_currency=tx["currency_from"],
        receiver_currency=tx["currency_to"],
        idempotency_key=str(uuid4())
    )