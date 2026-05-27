from adapters.base.canonical_execution import (
    CanonicalExecutionState
)

from .states import PAYSTACK_TO_CANONICAL


def map_paystack_state(status):

    state = PAYSTACK_TO_CANONICAL.get(
        status.lower(),
        "EXECUTION_STATE_UNKNOWN"
    )

    return CanonicalExecutionState[state]