# ==============================
# routing/execution_plan.py
# RailOne Execution Plan
# ==============================

from dataclasses import (
    dataclass,
    field
)

from typing import (
    List,
    Dict,
    Optional
)


@dataclass
class ExecutionPlan:

    utt_id: str

    routes: List[Dict]

    max_attempts: int = 5

    attempts_used: int = 0

    successful_route: Optional[Dict] = None

    failed_routes: List[Dict] = field(
        default_factory=list
    )

    # --------------------------
    # NEXT ROUTE
    # --------------------------
    def next_route(self):

        if not self.routes:

            return None

        if self.attempts_used >= self.max_attempts:

            return None

        self.attempts_used += 1

        return self.routes.pop(0)

    # --------------------------
    # FAIL ROUTE
    # --------------------------
    def fail_route(

        self,

        route,

        reason
    ):

        route["failure_reason"] = reason

        self.failed_routes.append(
            route
        )

    # --------------------------
    # SUCCESS ROUTE
    # --------------------------
    def succeed_route(

        self,

        route
    ):

        self.successful_route = route

    # --------------------------
    # FINALIZED
    # --------------------------
    def finalized(self):

        return (

            self.successful_route
            is not None
        )