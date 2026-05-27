from enum import Enum


class CanonicalExecutionState(Enum):

    EXECUTION_INITIATED = "execution_initiated"

    EXECUTION_ACKNOWLEDGED = "execution_acknowledged"

    EXECUTION_IN_PROGRESS = "execution_in_progress"

    EXECUTION_PENDING_EXTERNAL_SETTLEMENT = (
        "execution_pending_external_settlement"
    )

    EXECUTION_SETTLED = "execution_settled"

    EXECUTION_REVERSED = "execution_reversed"

    EXECUTION_REJECTED = "execution_rejected"

    EXECUTION_TIMEOUT = "execution_timeout"

    EXECUTION_REQUIRES_RECOVERY = (
        "execution_requires_recovery"
    )

    EXECUTION_REPLAY_BLOCKED = (
        "execution_replay_blocked"
    )

    EXECUTION_STATE_UNKNOWN = (
        "execution_state_unknown"
    )