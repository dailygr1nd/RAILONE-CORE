# ==============================
# checkpoint_engine.py
# RailOne Continuity Checkpoint Engine
# ==============================

from datetime import datetime, timezone

from db import SessionLocal

from execution.event_store import ExecutionEvent


# ==========================================
# CREATE CHECKPOINT
# ==========================================
def create_checkpoint(

    continuity_uid,

    utt_id,

    rtt_id,

    checkpoint_type,

    state,

    payload=None,

    replay_generation=0
):

    session = SessionLocal()

    try:

        checkpoint_event = ExecutionEvent(

            utt_id=utt_id,

            continuity_uid=continuity_uid,

            rtt_id=rtt_id,

            event_type="CHECKPOINT",

            previous_state=state,

            new_state=state,

            replay_generation=replay_generation,

            payload={

                "checkpoint_type":
                    checkpoint_type,

                "checkpoint_created_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

                "payload":
                    payload or {}
            }
        )

        session.add(checkpoint_event)

        session.commit()

        print(
            f"📍 Checkpoint Created → "
            f"{checkpoint_type}"
        )

        return {

            "success": True,

            "checkpoint_type":
                checkpoint_type
        }

    except Exception as e:

        session.rollback()

        return {

            "success": False,

            "error": str(e)
        }

    finally:

        session.close()


# ==========================================
# LOAD LAST CHECKPOINT
# ==========================================
def load_latest_checkpoint(
    continuity_uid
):

    session = SessionLocal()

    try:

        checkpoint = (

            session.query(ExecutionEvent)

            .filter(
                ExecutionEvent.continuity_uid
                == continuity_uid
            )

            .filter(
                ExecutionEvent.event_type
                == "CHECKPOINT"
            )

            .order_by(
                ExecutionEvent.created_at.desc()
            )

            .first()
        )

        if not checkpoint:

            return {

                "success": False,

                "error": "NO_CHECKPOINT_FOUND"
            }

        return {

            "success": True,

            "checkpoint": {

                "utt_id":
                    checkpoint.utt_id,

                "rtt_id":
                    checkpoint.rtt_id,

                "continuity_uid":
                    checkpoint.continuity_uid,

                "payload":
                    checkpoint.payload,

                "created_at":
                    checkpoint.created_at.isoformat()
            }
        }

    except Exception as e:

        return {

            "success": False,

            "error": str(e)
        }

    finally:

        session.close()


# ==========================================
# CHECKPOINT SUMMARY
# ==========================================
def summarize_checkpoint(
    continuity_uid
):

    result = load_latest_checkpoint(
        continuity_uid
    )

    if not result["success"]:

        print(
            "❌ No checkpoint found"
        )

        return

    checkpoint = result["checkpoint"]

    print("\n================================")
    print("📍 CONTINUITY CHECKPOINT")
    print("================================")

    print(
        f"Continuity ID: "
        f"{checkpoint['continuity_uid']}"
    )

    print(
        f"UTT ID: "
        f"{checkpoint['utt_id']}"
    )
    print(
        f"RTT ID: "
        f"{checkpoint['rtt_id']}"
    )

    print(
        f"Created At: "
        f"{checkpoint['created_at']}"
    )

    print(
        f"Checkpoint Payload:"
    )

    print(
        checkpoint["payload"]
    )