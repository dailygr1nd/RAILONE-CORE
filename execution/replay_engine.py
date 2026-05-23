# ==============================
# execution/replay_engine.py
# RailOne Replay Reconstruction
# Execution Continuity Recovery
# ==============================

from ledger.db import SessionLocal

from execution.event_models import (
    ExecutionEvent
)

from execution.checkpoint_models import (
    ExecutionCheckpoint
)


# ==========================================
# REPLAY EXECUTION CONTINUITY
# ==========================================
def replay_execution(

    utt_id,

    replay_generation=None
):

    session = SessionLocal()

    try:

        print(
            f"🔁 Replaying Execution "
            f"{utt_id}"
        )

        # --------------------------------
        # LOAD CHECKPOINTS
        # --------------------------------
        checkpoint_query = (

            session.query(
                ExecutionCheckpoint
            )

            .filter_by(
                utt_id=utt_id
            )
        )

        if replay_generation is not None:

            checkpoint_query = (

                checkpoint_query.filter_by(
                    replay_generation=
                        replay_generation
                )
            )

        checkpoints = (

            checkpoint_query.order_by(
                ExecutionCheckpoint.created_at
            )

            .all()
        )

        # --------------------------------
        # LOAD EXECUTION EVENTS
        # --------------------------------
        event_query = (

            session.query(
                ExecutionEvent
            )

            .filter_by(
                utt_id=utt_id
            )
        )

        if replay_generation is not None:

            event_query = (

                event_query.filter_by(
                    replay_generation=
                        replay_generation
                )
            )

        events = (

            event_query.order_by(
                ExecutionEvent.created_at
            )

            .all()
        )

        print(
            f"📦 Checkpoints: "
            f"{len(checkpoints)}"
        )

        print(
            f"📜 Events: "
            f"{len(events)}"
        )

        # --------------------------------
        # RECONSTRUCT EXECUTION LINEAGE
        # --------------------------------
        for event in events:

            print(

                f"[{event.created_at}] "

                f"{event.previous_state} "

                f"→ "

                f"{event.new_state}"

                f" | RTT={event.rtt_id}"

                f" | GEN={event.replay_generation}"
            )

        return {

            "utt_id":
                utt_id,

            "rtt_id":
                events[0].rtt_id
                if events else None,

            "continuity_uid":
                events[0].continuity_uid
                if events else None,

            "events":
                len(events),

            "checkpoints":
                len(checkpoints),

            "replay_generation":
                replay_generation,

            "reconstructed":
                True
        }

    finally:

        session.close()