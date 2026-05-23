# ==============================
# execution/continuity_reconstructor.py
# RailOne Continuity Reconstruction
# Deterministic Execution Replay
# ==============================

from ledger.db import SessionLocal

from execution.event_models import (
    ExecutionEvent
)


# ==========================================
# RECONSTRUCT EXECUTION CONTINUITY
# ==========================================
def reconstruct_continuity(

    continuity_uid
):

    session = SessionLocal()

    try:

        # --------------------------------
        # LOAD ORDERED EXECUTION EVENTS
        # --------------------------------
        events = (

            session.query(ExecutionEvent)

            .filter(
                ExecutionEvent.continuity_uid
                == continuity_uid
            )

            .order_by(
                ExecutionEvent.created_at.asc()
            )

            .all()
        )

        # --------------------------------
        # NO CONTINUITY FOUND
        # --------------------------------
        if not events:

            return {

                "success": False,

                "error":
                    "CONTINUITY_NOT_FOUND"
            }

        # ==========================================
        # RECONSTRUCT EXECUTION CONTEXT
        # ==========================================
        reconstructed = {

            # --------------------------------
            # IDENTITY CONTINUITY
            # --------------------------------
            "continuity_uid":
                continuity_uid,

            # --------------------------------
            # EXECUTION CONTINUITY
            # --------------------------------
            "utt_id": None,

            # --------------------------------
            # ROUTE REALIZATION
            # --------------------------------
            "rtt_id": None,

            # --------------------------------
            # EXECUTION STATE
            # --------------------------------
            "current_state": None,

            # --------------------------------
            # REPLAY LINEAGE
            # --------------------------------
            "replay_generation": 0,

            "lineage_parent": None,

            # --------------------------------
            # EXECUTION METRICS
            # --------------------------------
            "event_count":
                len(events),

            "lineage": [],

            # --------------------------------
            # EXECUTION CONTEXT
            # --------------------------------
            "metadata": {},

            "attestations": [],

            "route_context": None,

            "settlement_reference":
                None,

            # --------------------------------
            # EXECUTION TIMELINE
            # --------------------------------
            "created_at": None,

            "updated_at": None
        }

        # ==========================================
        # PROCESS EXECUTION EVENTS
        # ==========================================
        for event in events:

            payload = (
                event.payload or {}
            )

            # --------------------------------
            # CORE EXECUTION CONTINUITY
            # --------------------------------
            reconstructed["utt_id"] = (
                event.utt_id
            )

            reconstructed["rtt_id"] = (
                event.rtt_id
            )

            reconstructed["current_state"] = (
                event.new_state
            )

            reconstructed[
                "replay_generation"
            ] = max(

                reconstructed[
                    "replay_generation"
                ],

                event.replay_generation
            )

            reconstructed[
                "lineage_parent"
            ] = event.lineage_parent

            # --------------------------------
            # EXECUTION TIMELINE
            # --------------------------------
            reconstructed["updated_at"] = (

                event.created_at.isoformat()
            )

            if not reconstructed[
                "created_at"
            ]:

                reconstructed[
                    "created_at"
                ] = (

                    event.created_at
                    .isoformat()
                )

            # --------------------------------
            # BUILD EXECUTION LINEAGE
            # --------------------------------
            reconstructed["lineage"].append({

                "event_type":
                    event.event_type,

                "previous_state":
                    event.previous_state,

                "new_state":
                    event.new_state,

                "rtt_id":
                    event.rtt_id,

                "lineage_parent":
                    event.lineage_parent,

                "replay_generation":
                    event.replay_generation,

                "timestamp":
                    event.created_at
                    .isoformat()
            })

            # ==========================================
            # EVENT-SPECIFIC RECONSTRUCTION
            # ==========================================

            # --------------------------------
            # METADATA CONTEXT
            # --------------------------------
            if event.event_type == (
                "METADATA_ATTACHED"
            ):

                reconstructed[
                    "metadata"
                ].update(payload)

            # --------------------------------
            # EXECUTION ATTESTATIONS
            # --------------------------------
            elif event.event_type == (
                "ATTESTATION_ADDED"
            ):

                reconstructed[
                    "attestations"
                ].append(payload)

            # --------------------------------
            # ROUTE CONTEXT
            # --------------------------------
            elif event.event_type == (
                "ROUTE_CONTEXT_ATTACHED"
            ):

                reconstructed[
                    "route_context"
                ] = payload

            # --------------------------------
            # SETTLEMENT CONTEXT
            # --------------------------------
            elif event.event_type == (
                "SETTLEMENT_REFERENCE_ATTACHED"
            ):

                reconstructed[
                    "settlement_reference"
                ] = payload

        return {

            "success": True,

            "continuity":
                reconstructed
        }

    except Exception as e:

        return {

            "success": False,

            "error":
                str(e)
        }

    finally:

        session.close()


# ==========================================
# EXECUTION REPLAY SUMMARY
# ==========================================
def summarize_continuity(

    continuity_uid
):

    result = reconstruct_continuity(

        continuity_uid
    )

    if not result["success"]:

        return result

    continuity = result["continuity"]

    print(
        "\n================================"
    )

    print(
        "🔁 EXECUTION RECONSTRUCTION"
    )

    print(
        "================================"
    )

    print(
        f"Continuity UID: "
        f"{continuity['continuity_uid']}"
    )

    print(
        f"UTT ID: "
        f"{continuity['utt_id']}"
    )

    print(
        f"RTT ID: "
        f"{continuity['rtt_id']}"
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

    print("\n📜 EXECUTION LINEAGE")

    for item in continuity["lineage"]:

        print(

            f"{item['timestamp']} | "

            f"{item['event_type']} | "

            f"RTT={item['rtt_id']} | "

            f"GEN={item['replay_generation']} | "

            f"{item['previous_state']} "

            f"→ "

            f"{item['new_state']}"
        )

    return continuity