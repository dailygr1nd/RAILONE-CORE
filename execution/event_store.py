# ==============================
# execution/event_store.py
# RailOne Event Store
# ==============================

from db import SessionLocal

from execution.event_models import (
    ExecutionEvent
)


# ==========================================
# EMIT EVENT
# ==========================================
def emit_event(

    tx_id,

    event_type,

    previous_state=None,

    new_state=None,

    continuity_id=None,

    payload=None
):

    session = SessionLocal()

    try:

        event = ExecutionEvent(

            tx_id=tx_id,

            continuity_id=
                continuity_id,

            event_type=
                event_type,

            previous_state=
                previous_state,

            new_state=
                new_state,

            payload=
                payload or {}
        )

        session.add(event)

        session.commit()

    finally:

        session.close()