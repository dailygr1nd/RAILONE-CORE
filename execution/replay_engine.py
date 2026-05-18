# ==============================
# execution/replay_engine.py
# RailOne Replay Reconstruction
# ==============================

from db import SessionLocal

from execution.event_models import (
    ExecutionEvent
)

from execution.checkpoint_models import (
    ExecutionCheckpoint
)


# ==========================================
# REPLAY EXECUTION
# ==========================================
def replay_transaction(tx_id):

    session = SessionLocal()

    try:

        print(
            f"🔁 Replaying TX {tx_id}"
        )

        checkpoints = (

            session.query(
                ExecutionCheckpoint
            )

            .filter_by(tx_id=tx_id)

            .all()
        )

        events = (

            session.query(
                ExecutionEvent
            )

            .filter_by(tx_id=tx_id)

            .order_by(
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

        for event in events:

            print(

                f"[{event.created_at}] "

                f"{event.previous_state} "

                f"→ "

                f"{event.new_state}"
            )

        return {

            "tx_id": tx_id,

            "events": len(events),

            "checkpoints":
                len(checkpoints),

            "reconstructed": True
        }

    finally:

        session.close()