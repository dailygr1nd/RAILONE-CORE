# ==============================
# event_emitter.py
# RailOne Event Emitter
# ==============================

from db import SessionLocal

from execution.event_store import ExecutionEvent


def emit_event(

    utt_id,

    event_type,

    provider=None,

    provider_reference=None,

    canonical_state=None,

    replay_safe_hash=None,

    previous_state=None,

    new_state=None,

    continuity_uid=None,

    rtt_id=None,

    payload=None,

    lineage_parent=None,

    replay_generation=0
):

    session = SessionLocal()

    try:

        event = ExecutionEvent(

    utt_id=utt_id,

    rtt_id=rtt_id,

    continuity_uid=
        continuity_uid,

    event_type=
        event_type,

    provider=
        provider,

    provider_reference=
        provider_reference,

    canonical_state=
        canonical_state,

    replay_safe_hash=
        replay_safe_hash,

    previous_state=
        previous_state,

    new_state=
        new_state,

    payload=
        payload or {},

    lineage_parent=
        lineage_parent,

    replay_generation=
        replay_generation
)

        session.add(event)

        session.commit()

        return event

    except Exception:

        session.rollback()

        raise

    finally:

        session.close()