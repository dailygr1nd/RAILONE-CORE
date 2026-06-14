# ==============================
# routing/routing_engine.py
# RailOne Routing Engine
# ==============================

from routing import (
    rank_routes
)

from routing.execution_plan import (
    ExecutionPlan
)

from crypto.token_factory import (
    TokenFactory
)


class RoutingEngine:

    @staticmethod
    def build_execution_plan(

        utt_id,

        candidate_rails,

        amount,

        currency,

        cross_border=False,

        max_attempts=5
    ):

        ranked_routes = rank_routes(

            candidate_rails,

            amount,

            currency,

            cross_border
        )

        return ExecutionPlan(

            utt_id=utt_id,

            routes=ranked_routes,

            max_attempts=max_attempts
        )

    @staticmethod
    def create_rtt(

        utt_id,

        route,

        attempt,

        previous_route=None
    ):

        return TokenFactory.generate_rtt(

            utt_id=utt_id,

            attempt=attempt,

            selected_route=
                route["rail"],

            route_score=
                route["score"],

            previous_route=
                previous_route
        )