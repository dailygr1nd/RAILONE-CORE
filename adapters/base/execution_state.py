from enum import Enum


class CanonicalExecutionState(Enum):

    EXECUTION_INITIATED = (
        "execution_initiated"
    )

    EXECUTION_ACKNOWLEDGED = (
        "execution_acknowledged"
    )

    EXECUTION_IN_PROGRESS = (
        "execution_in_progress"
    )

    EXECUTION_PENDING_EXTERNAL_SETTLEMENT = (
        "execution_pending_external_settlement"
    )

    EXECUTION_SETTLED = (
        "execution_settled"
    )

    EXECUTION_REVERSED = (
        "execution_reversed"
    )

    EXECUTION_REJECTED = (
        "execution_rejected"
    )

    EXECUTION_TIMEOUT = (
        "execution_timeout"
    )

    EXECUTION_REQUIRES_RECOVERY = (
        "execution_requires_recovery"
    )

    EXECUTION_REPLAY_BLOCKED = (
        "execution_replay_blocked"
    )

    EXECUTION_STATE_UNKNOWN = (
        "execution_state_unknown"
    )


VALID_STATE_TRANSITIONS = {

    CanonicalExecutionState.EXECUTION_INITIATED: [
        CanonicalExecutionState.EXECUTION_ACKNOWLEDGED,
        CanonicalExecutionState.EXECUTION_REJECTED,
        CanonicalExecutionState.EXECUTION_TIMEOUT,
    ],

    CanonicalExecutionState.EXECUTION_ACKNOWLEDGED: [
        CanonicalExecutionState.EXECUTION_IN_PROGRESS,
        CanonicalExecutionState.EXECUTION_SETTLED,
        CanonicalExecutionState.EXECUTION_REQUIRES_RECOVERY,
    ],

    CanonicalExecutionState.EXECUTION_IN_PROGRESS: [
        CanonicalExecutionState.EXECUTION_SETTLED,
        CanonicalExecutionState.EXECUTION_TIMEOUT,
        CanonicalExecutionState.EXECUTION_REVERSED,
    ],

    CanonicalExecutionState.EXECUTION_TIMEOUT: [
        CanonicalExecutionState.EXECUTION_REQUIRES_RECOVERY,
    ],

    CanonicalExecutionState.EXECUTION_REQUIRES_RECOVERY: [
        CanonicalExecutionState.EXECUTION_IN_PROGRESS,
        CanonicalExecutionState.EXECUTION_SETTLED,
        CanonicalExecutionState.EXECUTION_REJECTED,
    ],
}


def is_valid_transition(
    current_state,
    next_state
):

    allowed_states = VALID_STATE_TRANSITIONS.get(
        current_state,
        []
    )

    return next_state in allowed_states