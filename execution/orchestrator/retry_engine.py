# ==========================================
# execution/retry_engine.py
# Enterprise RTT Mutation Engine
# ==========================================

from uuid import uuid4

from routing.recovery.replanning_engine import (
    ReplanningEngine
)

from routing.route_discovery import (
    RoutingEngine
)

from execution.events.event_store import (
    emit_event
)

from execution.application.execution_initiator import (
    initiate_transaction
)


def retry_execution(

    execution,
    failed_route,
    failure_reason
):

    if execution["state"] != "FAILED":

        raise Exception(

            "EXECUTION_NOT_FAILED"
        )

    next_routes = (

        ReplanningEngine.replan(

            execution,

            failed_route,

            failure_reason
        )
    )

    if not next_routes:

        raise Exception(

            "NO_ROUTES_AVAILABLE"
        )

    attempt = (

        execution.get(
            "replay_generation",
            0
        )

        + 1
    )

    selected_route = (
        next_routes[0]
    )

    rtt = RoutingEngine.create_rtt(

        utt_id=
            execution["utt_id"],

        route=
            selected_route,

        attempt=
            attempt,

        previous_route=
            failed_route["rail"]
    )

    emit_event(

        utt_id=
            execution["utt_id"],

        rtt_id=
            rtt["rtt_id"],

        continuity_uid=
            execution.get(
                "continuity_uid"
            ),

        event_type=
            "RTT_MUTATED",

        previous_state=
            "FAILED",

        new_state=
            "RETRYING",

        lineage_parent=
            execution.get(
                "rtt_id"
            ),

        replay_generation=
            attempt,

        payload={

            "failed_route":
                failed_route,

            "new_route":
                selected_route,

            "failure_reason":
                failure_reason
        }
    )

    return initiate_transaction(

        sender_account=
            execution[
                "sender_account"
            ],

        receiver_account=
            execution[
                "receiver_account"
            ],

        amount=
            execution[
                "amount"
            ],

        sender_currency=
            execution[
                "currency_from"
            ],

        receiver_currency=
            execution[
                "currency_to"
            ],

        retry=True,

        existing_utt=
            execution[
                "utt_id"
            ],

        rtt_id=
            rtt["rtt_id"],

        replay_generation=
            attempt
    )