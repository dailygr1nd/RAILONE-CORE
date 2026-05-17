from db import SessionLocal
from event_store import ExecutionEvent


def emit_event(
    tx_id,
    continuity_id,
    event_type,
    previous_state,
    new_state,
    payload=None,
    lineage_parent=None,
    replay_generation=0
):

    session = SessionLocal()

    try:

        event = ExecutionEvent(
            tx_id=tx_id,
            continuity_id=continuity_id,
            event_type=event_type,
            previous_state=previous_state,
            new_state=new_state,
            payload=payload or {},
            lineage_parent=lineage_parent,
            replay_generation=replay_generation
        )

        session.add(event)

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()