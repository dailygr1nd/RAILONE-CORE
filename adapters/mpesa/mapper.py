from adapters.base.canonical_execution import (
    CanonicalExecutionState
)

from .states import MPESA_TO_CANONICAL


def map_mpesa_state(result_code):

    state = MPESA_TO_CANONICAL.get(
        str(result_code),
        "EXECUTION_STATE_UNKNOWN"
    )

    return CanonicalExecutionState[state]