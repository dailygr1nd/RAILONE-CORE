# ==============================
# execution/retry_engine.py
# RailOne Retry Orchestrator
# ==============================

from uuid import uuid4

from routing import get_best_route

from transaction_engine import (
    initiate_transaction
)

from execution.event_store import (
    emit_event
)


# ==========================================
# RETRY FAILED EXECUTION
# ==========================================
def retry_transaction(tx):

    if tx["status"] != "FAILED":

        return {
            "error":
                "ONLY_FAILED_TX_CAN_BE_RETRIED"
        }

    print(
        f"🔁 Retrying TX "
        f"{tx['tx_id']}"
    )

    # ==========================================
    # RECOMPUTE EXECUTION ROUTE
    # ==========================================
    new_route = get_best_route(

        sender_currency=
            tx["currency_from"],

        receiver_currency=
            tx["currency_to"],

        amount=
            tx["amount"],

        sender_account=
            tx["sender_account"],

        receiver_account=
            tx["receiver_account"]
    )

    print(
        f"🛰️ New route: "
        f"{new_route}"
    )

    # ==========================================
    # EMIT RETRY EVENT
    # ==========================================
    emit_event(

        tx_id=tx["tx_id"],

        continuity_id=tx.get(
            "continuity_id"
        ),

        event_type="RETRY_INITIATED",

        previous_state="FAILED",

        new_state="RETRYING",

        payload={
            "new_route":
                new_route
        }
    )

    # ==========================================
    # RE-INITIATE EXECUTION
    # ==========================================
    return initiate_transaction(

        sender_account=
            tx["sender_account"],

        receiver_account=
            tx["receiver_account"],

        amount=
            tx["amount"],

        sender_currency=
            tx["currency_from"],

        receiver_currency=
            tx["currency_to"],

        idempotency_key=
            str(uuid4()),

        retry=True
    )