# ==========================================
# execution/execution_coordinator.py
# RailOne Execution Coordinator
# ==========================================

from routing.routing_engine import (
    RoutingEngine
)

from execution.execution_engine import (
    process_execution
)

from execution.event_emitter import (
    emit_event
)


class ExecutionCoordinator:

    @staticmethod
    def execute_plan(
        execution,
        execution_plan
    ):

        previous_route = None

        while not execution_plan.finalized():

            route = execution_plan.next_route()

            if route is None:

                emit_event(
                    utt_id=execution["utt_id"],
                    rtt_id=execution.get("rtt_id"),
                    continuity_uid=execution.get(
                        "continuity_uid"
                    ),
                    event_type="PLAN_EXHAUSTED",
                    previous_state="RETRYING",
                    new_state="FAILED"
                )

                return False

            rtt = RoutingEngine.create_rtt(

                utt_id=execution["utt_id"],

                route=route,

                attempt=
                    execution_plan.attempts_used,

                previous_route=
                    previous_route
            )

            execution["rtt_id"] = (
                rtt["rtt_id"]
            )

            execution["selected_route"] = (
                route
            )

            success = process_execution(
                execution
            )

            if success:

                execution_plan.succeed_route(
                    route
                )

                emit_event(
                    utt_id=execution["utt_id"],
                    rtt_id=rtt["rtt_id"],
                    continuity_uid=
                        execution.get(
                            "continuity_uid"
                        ),
                    event_type=
                        "ROUTE_SUCCEEDED",
                    previous_state=
                        "PROCESSING",
                    new_state=
                        "SETTLED",
                    payload=route
                )

                return True

            execution_plan.fail_route(

                route,

                "EXECUTION_FAILED"
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
                    "ROUTE_FAILED",

                previous_state=
                    "PROCESSING",

                new_state=
                    "RETRYING",

                payload=route
            )

            previous_route = route

        return False