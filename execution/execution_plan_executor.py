# ==============================
# execution/execution_plan_executor.py
# RailOne Execution Plan Executor
# ==============================

from routing.rtt_factory import (
    create_rtt
)

from execution.execution_result import (
    ExecutionResult
)

from execution.route_attempt_engine import (
    create_attempt,
    start_attempt,
    fail_attempt,
    settle_attempt
)

from execution.route_decision_engine import (
    mark_route_failed,
    mark_route_success
)

from provider.provider_registry import (
    ProviderRegistry
)


def execute_plan(

    execution_plan,
    continuity_uid
):

    previous_route = None

    while True:

        route = (
            execution_plan.next_route()
        )

        if route is None:

            return ExecutionResult(

                success=False,

                utt_id=
                    execution_plan.utt_id,

                rtt_id="NONE",

                attempt_number=
                    execution_plan.attempts_used,

                status=
                    "ATTEMPTS_EXHAUSTED",

                message=
                    "No viable routes remain"
            )

        rtt = create_rtt(

            utt_id=
                execution_plan.utt_id,

            route=route,

            attempt=
                execution_plan.attempts_used,

            previous_route=
                previous_route
        )

        rtt_id = rtt["rtt_id"]

        create_attempt(

            utt_id=
                execution_plan.utt_id,

            rtt_id=
                rtt_id,

            continuity_uid=
                continuity_uid,

            attempt_number=
                execution_plan.attempts_used,

            route=route
        )

        start_attempt(
            rtt_id
        )

        adapter = (

            ProviderRegistry.get(
                route["rail"]
            )
        )

        if not adapter:

            fail_attempt(

                rtt_id,

                "PROVIDER_NOT_FOUND"
            )

            execution_plan.fail_route(

                route,

                "PROVIDER_NOT_FOUND"
            )

            previous_route = (
                route["rail"]
            )

            continue

        result = adapter.execute(
            route
        )

        if result.success:

            settle_attempt(

                rtt_id=rtt_id,

                provider=
                    result.provider,

                provider_reference=
                    result.provider_reference,

                latency_ms=
                    result.latency_ms,

                provider_response=
                    result.payload
            )

            execution_plan.succeed_route(
                route
            )

            mark_route_success(
                rtt_id
            )

            return ExecutionResult(

                success=True,

                utt_id=
                    execution_plan.utt_id,

                rtt_id=
                    rtt_id,

                attempt_number=
                    execution_plan.attempts_used,

                status=
                    "SETTLED",

                provider=
                    result.provider,

                provider_reference=
                    result.provider_reference
            )

        fail_attempt(

            rtt_id,

            result.message,

            result.payload
        )

        mark_route_failed(

            rtt_id,

            result.message
        )

        execution_plan.fail_route(

            route,

            result.message
        )

        previous_route = (
            route["rail"]
        )