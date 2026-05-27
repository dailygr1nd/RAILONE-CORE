from adapters.base.canonical_execution import (
    CanonicalExecutionState
)

from .states import FLW_TO_CANONICAL


def map_flutterwave_state(status):

    state = FLW_TO_CANONICAL.get(
        status.lower(),
        "EXECUTION_STATE_UNKNOWN"
    )

    return CanonicalExecutionState[state]