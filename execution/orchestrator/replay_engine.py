# ==========================================
# execution/orchestrator/replay_engine.py
# ==========================================

from ledger.db import SessionLocal

from execution.events.event_models import (
    ExecutionEvent
)

from execution.checkpoints.checkpoint_models import (
    ExecutionCheckpoint
)


def replay_execution(utt_id):

    session = SessionLocal()

    try:

        checkpoints = (

            session.query(
                ExecutionCheckpoint
            )

            .filter_by(
                utt_id=utt_id
            )

            .order_by(
                ExecutionCheckpoint.created_at
            )

            .all()
        )

        events = (

            session.query(
                ExecutionEvent
            )

            .filter_by(
                utt_id=utt_id
            )

            .order_by(
                ExecutionEvent.created_at
            )

            .all()
        )

        if not checkpoints:

            raise Exception(
                "NO_CHECKPOINTS_FOUND"
            )

        latest_snapshot = (
            checkpoints[-1]
            .execution_snapshot
        )

        lineage = []

        for event in events:

            lineage.append({

                "event":
                    event.event_type,

                "rtt_id":
                    event.rtt_id,

                "state":
                    event.new_state,

                "generation":
                    event.replay_generation,

                "timestamp":
                    event.created_at
            })

        return {

            "utt_id":
                utt_id,

            "current_state":
                latest_snapshot.get(
                    "state"
                ),

            "lineage":
                lineage,

            "checkpoint_count":
                len(checkpoints),

            "event_count":
                len(events)
        }

    finally:

        session.close()