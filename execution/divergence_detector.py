from datetime import datetime

from execution.event_store import (
    emit_event
)

from execution.state_machine import (
    transition_state
)

from execution.continuity_reconstructor import (
    reconstruct_continuity
)

from execution.checkpoint_engine import (
    create_checkpoint
)


class DivergenceDetector:

    def __init__(
        self,
        provider_orchestrator
    ):

        self.provider_orchestrator = (
            provider_orchestrator
        )

    def analyze_execution_divergence(

        self,

        utt_id,

        provider_name
    ):

        continuity_snapshot = (
            reconstruct_continuity(
                utt_id
            )
        )

        provider_state = (

            self.provider_orchestrator
            .reconcile_execution(
                provider_name,
                utt_id
            )
        )

        divergence_report = (
            self._detect_divergence(

                continuity_snapshot,

                provider_state
            )
        )

        create_checkpoint(

            utt_id=utt_id,

            checkpoint_type=(
                "divergence_analysis"
            ),

            state_snapshot={

                "timestamp":
                    datetime.utcnow()
                    .isoformat(),

                "provider":
                    provider_name,

                "provider_state":
                    provider_state,

                "divergence_report":
                    divergence_report
            }
        )

        emit_event(

            utt_id=utt_id,

            event_type=(
                "DIVERGENCE_ANALYZED"
            ),

            provider=provider_name,

            payload=divergence_report
        )

        self._apply_divergence_state(
            utt_id,
            divergence_report
        )

        return divergence_report

    def _detect_divergence(

        self,

        continuity_snapshot,

        provider_state
    ):

        lineage = (
            continuity_snapshot
            .get("lineage", [])
        )

        latest_internal_state = (
            continuity_snapshot
            .get("latest_state")
        )

        provider_status = str(
            provider_state
        ).lower()

        divergence_type = None

        severity = "LOW"

        if (
            latest_internal_state
            == "SETTLED"
            and "failed" in provider_status
        ):

            divergence_type = (
                "INTERNAL_SETTLED_"
                "PROVIDER_FAILED"
            )

            severity = "CRITICAL"

        elif (
            latest_internal_state
            == "FAILED"
            and "success" in provider_status
        ):

            divergence_type = (
                "PROVIDER_SETTLED_"
                "INTERNAL_FAILED"
            )

            severity = "CRITICAL"

        elif (
            latest_internal_state
            == "REPLAY_REQUIRED"
            and "pending" in provider_status
        ):

            divergence_type = (
                "PROVIDER_PENDING_"
                "REPLAY_INITIATED"
            )

            severity = "MEDIUM"

        elif (
            latest_internal_state
            == "RECONCILIATION_PENDING"
            and "success" in provider_status
        ):

            divergence_type = (
                "LATE_PROVIDER_FINALITY"
            )

            severity = "HIGH"

        else:

            divergence_type = (
                "NO_SIGNIFICANT_DIVERGENCE"
            )

        return {

            "divergence_detected":

                divergence_type
                != "NO_SIGNIFICANT_DIVERGENCE",

            "divergence_type":
                divergence_type,

            "severity":
                severity,

            "internal_state":
                latest_internal_state,

            "provider_state":
                provider_status,

            "lineage_depth":
                len(lineage)
        }

    def _apply_divergence_state(

        self,

        utt_id,

        divergence_report
    ):

        divergence_type = (
            divergence_report[
                "divergence_type"
            ]
        )

        severity = (
            divergence_report[
                "severity"
            ]
        )

        if severity == "CRITICAL":

            transition_state(

                utt_id,

                "MANUAL_REVIEW_REQUIRED"
            )

            emit_event(

                utt_id=utt_id,

                event_type=(
                    "CRITICAL_DIVERGENCE_"
                    "DETECTED"
                ),

                payload=divergence_report
            )

            return

        if severity == "HIGH":

            transition_state(

                utt_id,

                "RECONCILIATION_PENDING"
            )

            emit_event(

                utt_id=utt_id,

                event_type=(
                    "HIGH_DIVERGENCE_"
                    "DETECTED"
                ),

                payload=divergence_report
            )

            return

        if severity == "MEDIUM":

            transition_state(

                utt_id,

                "REPLAY_REQUIRED"
            )

            emit_event(

                utt_id=utt_id,

                event_type=(
                    "MEDIUM_DIVERGENCE_"
                    "DETECTED"
                ),

                payload=divergence_report
            )

            return

        emit_event(

            utt_id=utt_id,

            event_type=(
                "NO_SIGNIFICANT_"
                "DIVERGENCE"
            ),

            payload=divergence_report
        )