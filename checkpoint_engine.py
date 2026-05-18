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

    continuity_id,

    tx_id,

    checkpoint_type,

    state,

    payload=None,

    replay_generation=0
):

    session = SessionLocal()

    try:

        checkpoint_event = ExecutionEvent(

            tx_id=tx_id,

            continuity_id=continuity_id,

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
    continuity_id
):

    session = SessionLocal()

    try:

        checkpoint = (

            session.query(ExecutionEvent)

            .filter(
                ExecutionEvent.continuity_id
                == continuity_id
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

                "tx_id":
                    checkpoint.tx_id,

                "continuity_id":
                    checkpoint.continuity_id,

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
    continuity_id
):

    result = load_latest_checkpoint(
        continuity_id
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
        f"{checkpoint['continuity_id']}"
    )

    print(
        f"TX ID: "
        f"{checkpoint['tx_id']}"
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