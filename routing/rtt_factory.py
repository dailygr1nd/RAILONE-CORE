# ==============================
# routing/rtt_factory.py
# RailOne RTT Factory
# ==============================

from crypto.token_factory import (
    TokenFactory
)


def create_rtt(

    utt_id,
    route,
    attempt,
    previous_route=None
):

    reason = {

        "latency":
            route.get(
                "latency_score"
            ),

        "liquidity":
            route.get(
                "liquidity_score"
            ),

        "congestion":
            route.get(
                "congestion_score"
            ),

        "throughput":
            route.get(
                "throughput_score"
            ),

        "cost":
            route.get(
                "cost_score"
            )
    }

    artifact = (

        TokenFactory.generate_rtt(

            utt_id=utt_id,

            attempt=attempt,

            selected_route=
                route["rail"],

            route_score=
                route["score"],

            previous_route=
                previous_route
        )
    )

    return {

        "rtt_id":
            artifact["rtt_id"],

        "payload":
            artifact["payload"],

        "route_reason":
            reason,

        "status":
            "ACTIVE"
    }