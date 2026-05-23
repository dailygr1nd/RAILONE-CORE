# ==============================
# identity/user_service.py
# RailOne Continuity User Service
# ==============================

from db import SessionLocal

from identity.models import User

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

        # ==========================================
        # EXISTING USER
        # ==========================================
        existing = (

            session.query(User)

            .filter_by(
                national_id=national_id
            )

            .first()
        )

        if existing:

            return {

                "existing": True,

                "railone_id":
                    existing.railone_id,

                "continuity_uid":
                    existing.continuity_uid,

                "full_name":
                    existing.full_name,

                "national_id":
                    existing.national_id,

                "trust_tier":
                    existing.trust_tier,

                "corridor":
                    existing.corridor
            }

        # ==========================================
        # GENERATE CONTINUITY IDENTITY
        # ==========================================
        identity = generate_railone_identity(

            corridor=corridor,

            trust_tier="T2",

            revision=1
        )

        # ==========================================
        # CREATE USER
        # ==========================================
        user = User(

            railone_id=
                identity["railone_id"],

            continuity_uid=
                identity["continuity_uid"],

            rig_id=
                identity["rig"],

            rio_id=
                identity["rio"],

            active_riv_id=
                identity["riv"],

            corridor=
                identity["corridor"],

            trust_tier=
                identity["trust_tier"],

            revision=
                identity["revision"],

            full_name=
                name,

            national_id=
                national_id,

            kyc_status=
                "VERIFIED"
        )

        session.add(user)

        session.commit()

        return {

            "existing": False,

            "railone_id":
                identity["railone_id"],

            "continuity_uid":
                identity["continuity_uid"],

            "full_name":
                name,

            "national_id":
                national_id,

            "trust_tier":
                identity["trust_tier"],

            "corridor":
                identity["corridor"]
        }

    finally:

        session.close()


# ==========================================
# LOOKUP USER
# ==========================================
def get_railone_id_by_national_id(
    national_id
):

    session = SessionLocal()

    try:

        user = (

            session.query(User)

            .filter_by(
                national_id=national_id
            )

            .first()
        )

        if not user:
            return None

        return user.railone_id

    finally:

        session.close()