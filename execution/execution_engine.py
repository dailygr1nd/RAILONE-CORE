# ==============================
# execution/execution_engine.py
# RailOne Deterministic
# Execution Orchestrator
# ==============================

from ledger.db import SessionLocal

from ledger.ledger_service import (
    apply_execution
)

from crypto.token_factory import (
    TokenFactory
)

from execution.execution_verifier import (
    verify_execution
)

from execution.execution_queue import (
    update_execution
)

from mirrored_available_state_engine import (
    release_funds
)

from webhook_dispatcher import (
    dispatch_event
)

from audit import log_event

from execution.event_emitter import (
    emit_event
)

from execution.checkpoint_engine import (
    create_checkpoint
)


# ==========================================
# PROCESS EXECUTION
# ==========================================
def process_execution(execution):

    session = SessionLocal()

    try:

        # ==========================================
        # PRE-EXECUTION VERIFICATION
        # ==========================================
        verification = verify_execution(
            execution
        )

        if not verification["valid"]:

            raise Exception(

                f"EXECUTION_VERIFICATION_FAILED: "

                f"{verification['checks']}"
            )

        # ==========================================
        # RTT VERIFICATION
        # ==========================================
        payload = execution[
            "payload_rtt"
        ]

        signature = bytes.fromhex(

            execution[
                "rtt_signature"
            ]
        )

        if not TokenFactory.verify(

            payload,

            signature,

            "R1CORE"
        ):

            raise Exception(
                "RTT_VERIFICATION_FAILED"
            )

        # ==========================================
        # EXECUTION START EVENT
        # ==========================================
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
                "EXECUTION_STARTED",

            previous_state=
                execution.get(
                    "state"
                ),

            new_state=
                "EXECUTION_STARTED"
        )

        # ==========================================
        # APPLY EXECUTION TO LEDGER
        # ==========================================
        apply_execution(

            session,

            execution
        )

        # ==========================================
        # EXECUTION FINALITY
        # ==========================================
        execution["state"] = (
            "SETTLED"
        )

        update_execution(

            execution["utt_id"],

            {

                "state":
                    "SETTLED"
            }
        )

        # ==========================================
        # CREATE FINAL CHECKPOINT
        # ==========================================
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
                "SETTLED",

            replay_generation=
                execution.get(
                    "replay_generation",
                    0
                ),

            snapshot=
                execution
        )

        # ==========================================
        # EXECUTION SUCCESS EVENT
        # ==========================================
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
                "EXECUTION_SETTLED",

            previous_state=
                "EXECUTION_STARTED",

            new_state=
                "SETTLED"
        )

        session.commit()

        log_event(

            "EXECUTION_SETTLED",

            execution
        )

        dispatch_event(

            execution,

            "execution.settled"
        )

        print(

            f"✅ Execution Settled: "

            f"{execution['utt_id']}"
        )

        return True

    except Exception as e:

        session.rollback()

        error = str(e)

        print(
            f"❌ Execution failed: "
            f"{error}"
        )

        # ==========================================
        # RELEASE LOCKED FUNDS
        # ==========================================
        try:

            release_funds(

                session,

                execution[
                    "sender_account"
                ],

                execution[
                    "gross_amount"
                ]
            )

            session.commit()

            print(

                f"🔓 Released locked funds: "

                f"{execution['gross_amount']}"
            )

        except Exception as rollback_error:

            session.rollback()

            print(

                f"❌ Rollback failed: "

                f"{rollback_error}"
            )

        # ==========================================
        # EXECUTION FAILURE STATE
        # ==========================================
        execution["state"] = (
            "FAILED"
        )

        execution[
            "failure_reason"
        ] = error

        update_execution(

            execution["utt_id"],

            {

                "state":
                    "FAILED"
            }
        )

        # ==========================================
        # FAILURE EVENT
        # ==========================================
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
                execution.get(
                    "state"
                ),

            new_state=
                "FAILED",

            payload={
                "error": error
            }
        )

        # ==========================================
        # FAILURE CHECKPOINT
        # ==========================================
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

            replay_generation=
                execution.get(
                    "replay_generation",
                    0
                ),

            snapshot=
                execution
        )

        log_event(

            "EXECUTION_FAILED",

            execution
        )

        dispatch_event(

            execution,

            "execution.failed"
        )

        return False

    finally:

        session.close()