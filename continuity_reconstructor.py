# ==============================
# continuity_reconstructor.py
# RailOne Continuity Reconstruction Engine
# ==============================

from db import SessionLocal

from event_store import ExecutionEvent


# ==========================================
# RECONSTRUCT CONTINUITY
# ==========================================
def reconstruct_continuity(
    continuity_id
):

    session = SessionLocal()

    try:

        # --------------------------------
        # LOAD ORDERED EVENTS
        # --------------------------------
        events = (

            session.query(ExecutionEvent)

            .filter(
                ExecutionEvent.continuity_id
                == continuity_id
            )

            .order_by(
                ExecutionEvent.created_at.asc()
            )

            .all()
        )

        if not events:

            return {
                "success": False,
                "error": "CONTINUITY_NOT_FOUND"
            }

        # --------------------------------
        # REBUILD STATE
        # --------------------------------
        reconstructed = {

            "continuity_id": continuity_id,

            "tx_id": None,

            "current_state": None,

            "replay_generation": 0,

            "event_count": len(events),

            "lineage": [],

            "metadata": {},

            "attestations": [],

            "route_context": None,

            "settlement_reference": None,

            "created_at": None,

            "updated_at": None
        }

        # --------------------------------
        # PROCESS EVENTS
        # --------------------------------
        for event in events:

            payload = event.payload or {}

            # --------------------------------
            # CORE CONTINUITY
            # --------------------------------
            reconstructed["tx_id"] = (
                event.tx_id
            )

            reconstructed["current_state"] = (
                event.new_state
            )

            reconstructed["replay_generation"] = max(
                reconstructed["replay_generation"],
                event.replay_generation
            )

            reconstructed["updated_at"] = (
                event.created_at.isoformat()
            )

            if not reconstructed["created_at"]:

                reconstructed["created_at"] = (
                    event.created_at.isoformat()
                )

            # --------------------------------
            # BUILD LINEAGE
            # --------------------------------
            reconstructed["lineage"].append({

                "event_type":
                    event.event_type,

                "previous_state":
                    event.previous_state,

                "new_state":
                    event.new_state,

                "timestamp":
                    event.created_at.isoformat(),

                "replay_generation":
                    event.replay_generation
            })

            # --------------------------------
            # EVENT-SPECIFIC RECONSTRUCTION
            # --------------------------------
            if event.event_type == (
                "METADATA_ATTACHED"
            ):

                reconstructed["metadata"].update(
                    payload
                )

            elif event.event_type == (
                "ATTESTATION_ADDED"
            ):

                reconstructed[
                    "attestations"
                ].append(payload)

            elif event.event_type == (
                "ROUTE_CONTEXT_ATTACHED"
            ):

                reconstructed[
                    "route_context"
                ] = payload

            elif event.event_type == (
                "SETTLEMENT_REFERENCE_ATTACHED"
            ):

                reconstructed[
                    "settlement_reference"
                ] = payload

        return {

            "success": True,

            "continuity": reconstructed
        }

    except Exception as e:

        return {

            "success": False,

            "error": str(e)
        }

    finally:

        session.close()


# ==========================================
# REPLAY SUMMARY
# ==========================================
def summarize_continuity(
    continuity_id
):

    result = reconstruct_continuity(
        continuity_id
    )

    if not result["success"]:

        return result

    continuity = result["continuity"]

    print("\n================================")
    print("🔁 CONTINUITY RECONSTRUCTION")
    print("================================")

    print(
        f"Continuity ID: "
        f"{continuity['continuity_id']}"
    )

    print(
        f"TX ID: "
        f"{continuity['tx_id']}"
    )

    print(
        f"Current State: "
        f"{continuity['current_state']}"
    )

    print(
        f"Replay Generation: "
        f"{continuity['replay_generation']}"
    )

    print(
        f"Events: "
        f"{continuity['event_count']}"
    )

    print("\n📜 LINEAGE")

    for item in continuity["lineage"]:

        print(
            f"{item['timestamp']} | "
            f"{item['event_type']} | "
            f"{item['previous_state']} "
            f"→ "
            f"{item['new_state']}"
        )

    return continuity