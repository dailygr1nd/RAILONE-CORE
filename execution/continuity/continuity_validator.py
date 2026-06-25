

from execution.checkpoints.checkpoint_engine import (
    load_latest_checkpoint
)



from execution.state.state_machine import (
    VALID_TRANSITIONS
)


class ContinuityValidator:

    def __init__(
        self,
        provider_orchestrator=None
    ):

        self.provider_orchestrator = (
            provider_orchestrator
        )

        if provider_orchestrator:

            self.divergence_detector = (
                DivergenceDetector(
                    provider_orchestrator
                )
            )

    def validate_continuity(

        self,

        continuity_uid,

        provider_name=None
    ):

        reconstruction = (
            reconstruct_continuity(
                continuity_uid
            )
        )

        if not reconstruction["success"]:

            return {

                "valid": False,

                "error": (
                    reconstruction["error"]
                )
            }

        continuity = (
            reconstruction["continuity"]
        )

        lineage = continuity["lineage"]

        validation_report = {

            "valid": True,

            "continuity_uid":
                continuity_uid,

            "checks": {},

            "warnings": [],

            "errors": []
        }

        # =====================================
        # VALIDATE REPLAY GENERATIONS
        # =====================================
        replay_check = (
            self
            ._validate_replay_generations(
                lineage
            )
        )

        validation_report[
            "checks"
        ][
            "replay_generations"
        ] = replay_check

        # =====================================
        # VALIDATE STATE TRANSITIONS
        # =====================================
        transition_check = (
            self
            ._validate_state_transitions(
                lineage
            )
        )

        validation_report[
            "checks"
        ][
            "state_transitions"
        ] = transition_check

        # =====================================
        # VALIDATE LINEAGE CONSISTENCY
        # =====================================
        lineage_check = (
            self
            ._validate_lineage_integrity(
                lineage
            )
        )

        validation_report[
            "checks"
        ][
            "lineage_integrity"
        ] = lineage_check

        # =====================================
        # VALIDATE CHECKPOINT CONSISTENCY
        # =====================================
        checkpoint_check = (
            self
            ._validate_checkpoint(
                continuity_uid,
                continuity
            )
        )

        validation_report[
            "checks"
        ][
            "checkpoint_consistency"
        ] = checkpoint_check

        # =====================================
        # PROVIDER DIVERGENCE ANALYSIS
        # =====================================
        if (
            provider_name
            and self.provider_orchestrator
        ):

            divergence_check = (

                self.divergence_detector
                .analyze_execution_divergence(

                    continuity_uid,

                    provider_name
                )
            )

            validation_report[
                "checks"
            ][
                "provider_divergence"
            ] = divergence_check

        # =====================================
        # EVALUATE FINAL VALIDITY
        # =====================================
        for check_name, result in (
            validation_report[
                "checks"
            ].items()
        ):

            if not result.get("valid", True):

                validation_report[
                    "valid"
                ] = False

                validation_report[
                    "errors"
                ].append(

                    f"{check_name} failed"
                )

        return validation_report

    def _validate_replay_generations(
        self,
        lineage
    ):

        previous_generation = -1

        for event in lineage:

            generation = event.get(
                "replay_generation",
                0
            )

            if generation < previous_generation:

                return {

                    "valid": False,

                    "reason": (
                        "Replay generation "
                        "regression detected"
                    )
                }

            previous_generation = generation

        return {

            "valid": True
        }

    def _validate_state_transitions(
        self,
        lineage
    ):

        for event in lineage:

            previous_state = event.get(
                "previous_state"
            )

            new_state = event.get(
                "new_state"
            )

            if (
                previous_state
                and new_state
            ):

                allowed = (
                    VALID_TRANSITIONS
                    .get(
                        previous_state,
                        []
                    )
                )

                if (
                    new_state
                    not in allowed
                ):

                    return {

                        "valid": False,

                        "reason": (

                            "Invalid state "
                            "transition detected"
                        ),

                        "transition": (

                            f"{previous_state}"
                            f" -> "
                            f"{new_state}"
                        )
                    }

        return {

            "valid": True
        }

    def _validate_lineage_integrity(
        self,
        lineage
    ):

        seen_timestamps = set()

        for event in lineage:

            timestamp = event.get(
                "timestamp"
            )

            if timestamp in seen_timestamps:

                return {

                    "valid": False,

                    "reason": (
                        "Duplicate lineage "
                        "event detected"
                    )
                }

            seen_timestamps.add(
                timestamp
            )

        return {

            "valid": True
        }

    def _validate_checkpoint(

        self,

        continuity_uid,

        continuity
    ):

        checkpoint = (
            load_latest_checkpoint(
                continuity_uid
            )
        )

        if not checkpoint:

            return {

                "valid": False,

                "reason": (
                    "No checkpoint found"
                )
            }

        checkpoint_state = (
            checkpoint.get(
                "current_state"
            )
        )

        continuity_state = (
            continuity.get(
                "current_state"
            )
        )

        if (
            checkpoint_state
            != continuity_state
        ):

            return {

                "valid": False,

                "reason": (
                    "Checkpoint continuity "
                    "state mismatch"
                ),

                "checkpoint_state":
                    checkpoint_state,

                "continuity_state":
                    continuity_state
            }

        return {

            "valid": True
        }