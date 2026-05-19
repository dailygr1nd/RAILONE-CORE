# ==============================
# identity/revision_engine.py
# RailOne Identity Revision Engine
# ==============================

from datetime import (
    datetime,
    timezone
)

from ledger.db import SessionLocal

from identity.models import (

    User,
    RIOObject,
    RIVObject,
    IdentityReplayEvent
)

from identity.identity_engine import (

    build_railone_id,
    generate_riv
)


# ==========================================
# CREATE NEW IDENTITY REVISION
# ==========================================
def create_identity_revision(

    continuity_uid,

    new_trust_tier=None,

    new_corridor=None,

    revision_reason="IDENTITY_UPDATE",

    revision_metadata=None
):

    session = SessionLocal()

    try:

        # --------------------------------
        # LOAD USER
        # --------------------------------
        user = (

            session.query(User)

            .filter_by(
                continuity_uid=continuity_uid
            )

            .first()
        )

        if not user:

            raise Exception(

                f"CONTINUITY_NOT_FOUND: "
                f"{continuity_uid}"
            )

        # --------------------------------
        # LOAD RIO
        # --------------------------------
        rio = (

            session.query(RIOObject)

            .filter_by(
                continuity_uid=continuity_uid
            )

            .first()
        )

        if not rio:

            raise Exception(

                f"RIO_NOT_FOUND: "
                f"{continuity_uid}"
            )

        # --------------------------------
        # DETERMINE NEW STATE
        # --------------------------------
        next_revision = (
            user.revision + 1
        )

        updated_trust_tier = (

            new_trust_tier

            if new_trust_tier

            else user.trust_tier
        )

        updated_corridor = (

            new_corridor

            if new_corridor

            else user.corridor
        )

        # --------------------------------
        # GENERATE NEW RIV
        # --------------------------------
        new_riv_id = generate_riv(

            continuity_uid,

            next_revision
        )

        # --------------------------------
        # GENERATE NEW RAILONE ID
        # --------------------------------
        new_railone_id = build_railone_id(

            corridor=updated_corridor,

            trust_tier=updated_trust_tier,

            continuity_uid=continuity_uid,

            revision=next_revision
        )

        # --------------------------------
        # CREATE RIV OBJECT
        # --------------------------------
        riv = RIVObject(

            riv_id=new_riv_id,

            rio_id=rio.rio_id,

            continuity_uid=
                continuity_uid,

            revision=next_revision,

            trust_tier=
                updated_trust_tier,

            revision_reason=
                revision_reason,

            revision_metadata=(
                revision_metadata
                or {}
            ),

            replay_generation=0
        )

        session.add(riv)

        # --------------------------------
        # REPLAY EVENT
        # --------------------------------
        replay_event = (

            IdentityReplayEvent(

                continuity_uid=
                    continuity_uid,

                rio_id=rio.rio_id,

                riv_id=new_riv_id,

                event_type=
                    "IDENTITY_REVISION",

                previous_state=
                    user.railone_id,

                new_state=
                    new_railone_id,

                payload={

                    "previous_revision":
                        user.revision,

                    "new_revision":
                        next_revision,

                    "previous_tier":
                        user.trust_tier,

                    "new_tier":
                        updated_trust_tier
                }
            )
        )

        session.add(replay_event)

        # --------------------------------
        # UPDATE USER
        # --------------------------------
        old_railone_id = (
            user.railone_id
        )

        user.railone_id = (
            new_railone_id
        )

        user.active_riv_id = (
            new_riv_id
        )

        user.revision = (
            next_revision
        )

        user.trust_tier = (
            updated_trust_tier
        )

        user.corridor = (
            updated_corridor
        )

        # --------------------------------
        # UPDATE RIO
        # --------------------------------
        rio.active_riv_id = (
            new_riv_id
        )

        rio.trust_tier = (
            updated_trust_tier
        )

        rio.corridor = (
            updated_corridor
        )

        session.commit()

        print(
            "\n🔄 Identity Revision Created"
        )

        print(
            f"📌 Continuity UID: "
            f"{continuity_uid}"
        )

        print(
            f"🆔 Previous ID: "
            f"{old_railone_id}"
        )

        print(
            f"🆕 New ID: "
            f"{new_railone_id}"
        )

        print(
            f"📚 Revision: "
            f"R{next_revision}"
        )

        return {

            "continuity_uid":
                continuity_uid,

            "previous_railone_id":
                old_railone_id,

            "new_railone_id":
                new_railone_id,

            "rio_id":
                rio.rio_id,

            "new_riv_id":
                new_riv_id,

            "revision":
                next_revision,

            "trust_tier":
                updated_trust_tier,

            "corridor":
                updated_corridor
        }

    finally:

        session.close()


# ==========================================
# GET IDENTITY REVISION HISTORY
# ==========================================
def get_revision_history(

    continuity_uid
):

    session = SessionLocal()

    try:

        revisions = (

            session.query(RIVObject)

            .filter_by(
                continuity_uid=continuity_uid
            )

            .order_by(
                RIVObject.revision.asc()
            )

            .all()
        )

        history = []

        for riv in revisions:

            history.append({

                "riv_id":
                    riv.riv_id,

                "revision":
                    riv.revision,

                "trust_tier":
                    riv.trust_tier,

                "reason":
                    riv.revision_reason,

                "created_at":
                    str(riv.created_at)
            })

        return history

    finally:

        session.close()