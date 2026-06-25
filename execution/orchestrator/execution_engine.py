from ledger.db import SessionLocal

from execution.execution_verifier import (
    verify_execution
)

from execution.events.event_store import (
    emit_event
)

from execution.checkpoints.checkpoint_engine import (
    create_checkpoint
)

from routing.recovery.failure_classifier import (
    classify_failure
)

from ledger.ledger_service import (
    apply_execution
)

from settlement.mirrored_available_state_engine import (
    release_funds
)


def process_execution(execution):

    session = SessionLocal()

    try:

        verification = verify_execution(
            execution
        )

        if not verification["valid"]:

            raise Exception(
                "EXECUTION_VERIFICATION_FAILED"
            )

        emit_event(

            utt_id=execution["utt_id"],

            rtt_id=execution["rtt_id"],

            continuity_uid=
                execution.get(
                    "continuity_uid"
                ),

            event_type=
                "EXECUTION_STARTED",

            previous_state=
                execution.get("state"),

            new_state=
                "PROCESSING"
        )

        apply_execution(
            session,
            execution
        )

        execution["state"] = (
            "SETTLED"
        )

        create_checkpoint(

            utt_id=
                execution["utt_id"],

            rtt_id=
                execution["rtt_id"],

            continuity_uid=
                execution.get(
                    "continuity_uid"
                ),

            checkpoint_state=
                "SETTLED",

            snapshot=
                execution
        )

        emit_event(

            utt_id=
                execution["utt_id"],

            rtt_id=
                execution["rtt_id"],

            continuity_uid=
                execution.get(
                    "continuity_uid"
                ),

            event_type=
                "EXECUTION_SETTLED",

            previous_state=
                "PROCESSING",

            new_state=
                "SETTLED"
        )

        session.commit()

        return {

            "success": True,

            "state": "SETTLED"
        }

    except Exception as e:

        session.rollback()

        release_funds(

            session,

            execution[
                "sender_account"
            ],

            execution[
                "gross_amount"
            ]
        )

        failure_type = (
            classify_failure(
                str(e)
            )
        )

        execution["state"] = (
            "FAILED"
        )

        execution[
            "failure_type"
        ] = failure_type

        create_checkpoint(

            utt_id=
                execution["utt_id"],

            rtt_id=
                execution.get(
                    "rtt_id"
                ),

            continuity_uid=
                execution.get(
                    "continuity_uid"
                ),

            checkpoint_state=
                "FAILED",

            snapshot=
                execution
        )

        emit_event(

            utt_id=
                execution["utt_id"],

            rtt_id=
                execution.get(
                    "rtt_id"
                ),

            continuity_uid=
                execution.get(
                    "continuity_uid"
                ),

            event_type=
                "EXECUTION_FAILED",

            previous_state=
                "PROCESSING",

            new_state=
                "FAILED",

            payload={

                "error":
                    str(e),

                "failure_type":
                    failure_type
            }
        )

        return {

            "success": False,

            "failure_type":
                failure_type,

            "error":
                str(e)
        }

    finally:

        session.close()