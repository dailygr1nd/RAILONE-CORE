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

    utt_id,

    event_type,

    previous_state=None,

    new_state=None,

    continuity_uid=None,

    rtt_id=None,

    payload=None
):

    session = SessionLocal()

    try:

        event = ExecutionEvent(

            utt_id=utt_id,

            continuity_uid=
                continuity_uid,

            rtt_id= rtt_id,    

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