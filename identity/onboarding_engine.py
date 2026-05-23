# ==============================
# identity/onboarding_engine.py
# RailOne Identity Continuity Engine
# ==============================

from uuid import uuid4

from ledger.db import SessionLocal

from identity.models import (

    User,
    RIGObject,
    RIOObject,
    RIVObject
)

from identity.identity_engine import (
    generate_railone_identity
)


# ==========================================
# ONBOARD USER
# ==========================================
def onboard_user(

    name,

    national_id,

    corridor="EA"
):

    session = SessionLocal()

    try:

        # --------------------------------
        # EXISTING USER
        # Continuity must be idempotent
        # --------------------------------
        existing = (

            session.query(User)

            .filter_by(
                national_id=national_id
            )

            .first()
        )

        if existing:

            print(
                f"⚠️ Existing continuity found "
                f"for {national_id}"
            )

            return {

                "existing": True,

                "railone_id":
                    existing.railone_id,

                "continuity_uid":
                    existing.continuity_uid,

                "rig":
                    existing.rig_id,

                "rio":
                    existing.rio_id,

                "riv":
                    existing.active_riv_id
            }

        # --------------------------------
        # GENERATE IDENTITY STACK
        # --------------------------------
        identity = generate_railone_identity(

            corridor=corridor,

            trust_tier="T2",

            revision=1
        )

        continuity_uid = (
            identity["continuity_uid"]
        )

        # --------------------------------
        # RIG
        # Immutable Genesis Anchor
        # --------------------------------
        rig = RIGObject(

            rig_id=
                identity["rig"],

            continuity_uid=
                continuity_uid,

            genesis_provider=
                "RAILONE",

            genesis_country=
                corridor,

            genesis_hash=
                str(uuid4())
        )

        session.add(rig)

        # --------------------------------
        # RIV
        # Initial Identity Revision
        # --------------------------------
        riv = RIVObject(

            riv_id=
                identity["riv"],

            rio_id=
                identity["rio"],

            continuity_uid=
                continuity_uid,

            revision=1,

            trust_tier=
                "T2",

            revision_reason=
                "INITIAL_ONBOARDING",

            replay_generation=0
        )

        session.add(riv)

        # --------------------------------
        # RIO
        # Canonical Continuity Object
        # --------------------------------
        rio = RIOObject(

            rio_id=
                identity["rio"],

            continuity_uid=
                continuity_uid,

            rig_id=
                identity["rig"],

            active_riv_id=
                identity["riv"],

            trust_tier=
                "T2",

            corridor=
                corridor,

            identity_state=
                "ACTIVE"
        )

        session.add(rio)

        # --------------------------------
        # USER
        # Public Identity Projection
        # --------------------------------
        user = User(

            railone_id=
                identity["railone_id"],

            continuity_uid=
                continuity_uid,

            rig_id=
                identity["rig"],

            rio_id=
                identity["rio"],

            active_riv_id=
                identity["riv"],

            corridor=
                corridor,

            trust_tier=
                "T2",

            revision=1,

            full_name=
                name,

            national_id=
                national_id,

            kyc_status=
                "VERIFIED"
        )

        session.add(user)

        # --------------------------------
        # COMMIT ALL CONTINUITY OBJECTS
        # --------------------------------
        session.commit()

        print(
            f"✅ Onboarded: "
            f"{identity['railone_id']}"
        )

        return {

            "existing": False,

            "railone_id":
                identity["railone_id"],

            "continuity_uid":
                continuity_uid,

            "rig":
                identity["rig"],

            "rio":
                identity["rio"],

            "riv":
                identity["riv"]
        }

    except Exception as e:

        session.rollback()

        print(
            f"\n❌ ONBOARDING FAILURE: {e}"
        )

        raise

    finally:

        session.close()