from datetime import datetime

from execution.event_store import (
    emit_event
)

from execution.state_machine import (
    transition_state
)

from execution.replay_engine import (
    replay_execution
)

from execution.retry_engine import (
    retry_execution
)

from execution.continuity_reconstructor import (
    reconstruct_continuity
)

from execution.checkpoint_engine import (
    load_latest_checkpoint,
    create_checkpoint
)


class ExecutionRecoveryEngine:

    def __init__(
        self,
        provider_orchestrator
    ):

        self.provider_orchestrator = (
            provider_orchestrator
        )

    def recover_execution(
        self,
        utt_id,
        provider_name,
        recovery_context=None
    ):

        emit_event(

            utt_id=utt_id,

            event_type=(
                "RECOVERY_INITIATED"
            ),

            provider=provider_name,

            canonical_state=(
                "execution_requires_recovery"
            ),

            payload={
                "recovery_context":
                    recovery_context
            }
        )

        transition_state(

            utt_id,

            "RECONCILIATION_PENDING"
        )

        continuity_snapshot = (
            self._reconstruct_continuity(
                utt_id
            )
        )

        replay_snapshot = (
            self._replay_execution(
                utt_id
            )
        )

        checkpoint_snapshot = (
            self._load_checkpoint(
                utt_id
            )
        )

        provider_state = (
            self._reconcile_provider_state(
                provider_name,
                utt_id
            )
        )

        recovery_decision = (
            self._analyze_recovery_state(

                continuity_snapshot,

                replay_snapshot,

                checkpoint_snapshot,

                provider_state
            )
        )

        create_checkpoint(

            utt_id=utt_id,

            checkpoint_type=(
                "recovery_analysis"
            ),

            state_snapshot={

                "timestamp":
                    datetime.utcnow()
                    .isoformat(),

                "provider":
                    provider_name,

                "recovery_decision":
                    recovery_decision,

                "provider_state":
                    provider_state,

                "continuity_snapshot":
                    continuity_snapshot
            }
        )

        emit_event(

            utt_id=utt_id,

            event_type=(
                "RECOVERY_ANALYZED"
            ),

            provider=provider_name,

            payload={
                "decision":
                    recovery_decision
            }
        )

        return self._execute_recovery_strategy(

            utt_id,

            provider_name,

            recovery_decision,

            provider_state
        )

    def _reconstruct_continuity(
        self,
        utt_id
    ):

        return reconstruct_continuity(
            utt_id
        )

    def _replay_execution(
        self,
        utt_id
    ):

        return replay_execution(
            utt_id
        )

    def _load_checkpoint(
        self,
        utt_id
    ):

        return load_latest_checkpoint(
            utt_id
        )

    def _reconcile_provider_state(
        self,
        provider_name,
        utt_id
    ):

        return (

            self.provider_orchestrator
            .reconcile_execution(
                provider_name,
                utt_id
            )
        )

    def _analyze_recovery_state(

        self,

        continuity_snapshot,

        replay_snapshot,

        checkpoint_snapshot,

        provider_state
    ):

        if not provider_state:

            return (
                "PROVIDER_UNREACHABLE"
            )

        provider_status = (
            str(provider_state)
            .lower()
        )

        if "success" in provider_status:

            return (
                "EXECUTION_ALREADY_SETTLED"
            )

        if "pending" in provider_status:

            return (
                "AWAIT_PROVIDER_FINALITY"
            )

        if "failed" in provider_status:

            return (
                "SAFE_TO_RETRY"
            )

        return (
            "MANUAL_RECONCILIATION_REQUIRED"
        )

    def _execute_recovery_strategy(

        self,

        utt_id,

        provider_name,

        recovery_decision,

        provider_state
    ):

        if (
            recovery_decision
            == "EXECUTION_ALREADY_SETTLED"
        ):

            transition_state(
                utt_id,
                "SETTLED"
            )

            emit_event(

                utt_id=utt_id,

                event_type=(
                    "RECOVERY_COMPLETED"
                ),

                provider=provider_name,

                payload={
                    "result":
                        "already_settled"
                }
            )

            return {

                "execution_id":
                    utt_id,

                "recovered": True,

                "result":
                    "already_settled"
            }

        if (
            recovery_decision
            == "AWAIT_PROVIDER_FINALITY"
        ):

            emit_event(

                utt_id=utt_id,

                event_type=(
                    "RECOVERY_WAITING"
                ),

                provider=provider_name
            )

            return {

                "execution_id":
                    utt_id,

                "recovered": False,

                "result":
                    "awaiting_finality"
            }

        if (
            recovery_decision
            == "SAFE_TO_RETRY"
        ):

            emit_event(

                utt_id=utt_id,

                event_type=(
                    "SAFE_RETRY_APPROVED"
                ),

                provider=provider_name
            )

            retry_result = retry_execution(
                utt_id
            )

            return {

                "execution_id":
                    utt_id,

                "recovered": True,

                "retry_result":
                    retry_result
            }

        transition_state(
            utt_id,
            "MANUAL_REVIEW_REQUIRED"
        )

        emit_event(

            utt_id=utt_id,

            event_type=(
                "MANUAL_RECONCILIATION_REQUIRED"
            ),

            provider=provider_name
        )

        return {

            "execution_id":
                utt_id,

            "recovered": False,

            "result":
                "manual_review_required"
        }