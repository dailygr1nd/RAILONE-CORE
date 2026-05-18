# ==============================
# identity/user_service.py
# RailOne Continuity User Service
# ==============================

from db import SessionLocal

from identity.models import User

from identity.identity_engine import (
    generate_railone_id
)


# ==========================================
# ONBOARD USER (CONTINUITY SAFE)
# ==========================================
def onboard_user(
    name,
    national_id
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
        # NEW CONTINUITY IDENTITY
        # ==========================================
        identity = generate_railone_id(

            corridor="EA",

            trust_tier="T2",

            revision=1
        )

        railone_id = identity["railone_id"]

        # ==========================================
        # CREATE USER
        # ==========================================
        user = User(

            railone_id=railone_id,

            continuity_uid=identity[
                "railone_id"
            ],

            rig_id=identity[
                "rig_id"
            ],

            rio_id=identity[
                "rio_id"
            ],

            active_riv_id=identity[
                "riv_id"
            ],

            corridor="EA",

            trust_tier="T2",

            revision=1,

            full_name=name,

            national_id=national_id,

            kyc_status="VERIFIED"
        )

        session.add(user)

        session.commit()

        return {

            "existing": False,

            "railone_id":
                railone_id,

            "full_name":
                name,

            "national_id":
                national_id,

            "trust_tier":
                "T2",

            "corridor":
                "EA"
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