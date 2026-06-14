# ==============================
# execution/retry_engine.py
# RailOne Deterministic Replay
# Route Mutation Orchestrator
# ==============================

from uuid import uuid4

from routing.routing import get_best_route

from execution.execution_initiator import (
    initiate_transaction
)

from execution.event_emitter import (
    emit_event
)


# ==========================================
# RETRY EXECUTION
# ==========================================
def retry_execution(execution):

    # --------------------------------
    # VALIDATE FAILURE STATE
    # --------------------------------
    if execution["state"] != "FAILED":

        return {

            "error":
                "ONLY_FAILED_EXECUTIONS_CAN_BE_REPLAYED"
        }

    print(
        f"🔁 Replaying Execution "
        f"{execution['utt_id']}"
    )

    # ==========================================
    # MUTATE ROUTE REALIZATION
    # ==========================================
    new_rtt_id = (

        f"RTT-"
        f"{uuid4().hex[:12].upper()}"
    )

    # ==========================================
    # RECOMPUTE ROUTE
    # ==========================================
    new_route = get_best_route(

        sender_currency=
            execution["currency_from"],

        receiver_currency=
            execution["currency_to"],

        amount=
            execution["amount"],

        sender_account=
            execution["sender_account"],

        receiver_account=
            execution["receiver_account"]
    )

    print(
        f"🛰️ New RTT: "
        f"{new_rtt_id}"
    )

    print(
        f"🛰️ New Route: "
        f"{new_route}"
    )

    # ==========================================
    # EMIT REPLAY EVENT
    # ==========================================
    emit_event(

        utt_id=
            execution["utt_id"],

        rtt_id=
            new_rtt_id,

        continuity_uid=
            execution.get(
                "continuity_uid"
            ),

        event_type=
            "REPLAY_INITIATED",

        previous_state=
            "FAILED",

        new_state=
            "REPLAY_REQUIRED",

        payload={

            "new_route":
                new_route,

            "previous_rtt":
                execution.get(
                    "rtt_id"
                )
        },

        lineage_parent=
            execution.get(
                "rtt_id"
            ),

        replay_generation=
            execution.get(
                "replay_generation",
                0
            ) + 1
    )

    # ==========================================
    # RE-INITIATE EXECUTION
    # ==========================================
    return initiate_transaction(

        sender_account=
            execution["sender_account"],

        receiver_account=
            execution["receiver_account"],

        amount=
            execution["amount"],

        sender_currency=
            execution["currency_from"],

        receiver_currency=
            execution["currency_to"],

        idempotency_key=
            str(uuid4()),

        retry=True,

        existing_utt=
            execution["utt_id"],

        rtt_id=
            new_rtt_id,

        replay_generation=
            execution.get(
                "replay_generation",
                0
            ) + 1
    )