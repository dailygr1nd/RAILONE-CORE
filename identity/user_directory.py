# ==============================
# identity/user_directory.py
# RailOne Continuity User Registry
# ==============================

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
# CREATE USER
# Continuity-safe onboarding projection
# ==========================================
def create_user(

    full_name: str,

    national_id: str,

    corridor: str = "EA"
):

    session = SessionLocal()

    try:

        # --------------------------------
        # EXISTING CONTINUITY CHECK
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

                "created": False,

                "railone_id":
                    existing.railone_id,

                "continuity_uid":
                    existing.continuity_uid,

                "rig":
                    existing.rig_id,

                "rio":
                    existing.rio_id,

                "riv":
                    existing.active_riv_id,

                "kyc_status":
                    existing.kyc_status
            }

        # --------------------------------
        # GENERATE CONTINUITY STACK
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
        # Immutable Genesis Identity
        # --------------------------------
        rig = RIGObject(

            rig_id=identity["rig"],

            continuity_uid=
                continuity_uid,

            genesis_provider=
                "RAILONE",

            genesis_country=
                corridor,

            genesis_hash=
                identity["rig"]
        )

        session.add(rig)

        # --------------------------------
        # RIV
        # Initial Identity Revision
        # --------------------------------
        riv = RIVObject(

            riv_id=identity["riv"],

            rio_id=identity["rio"],

            continuity_uid=
                continuity_uid,

            revision=1,

            trust_tier="T2",

            revision_reason=
                "INITIAL_ONBOARDING"
        )

        session.add(riv)

        # --------------------------------
        # RIO
        # Canonical Continuity Object
        # --------------------------------
        rio = RIOObject(

            rio_id=identity["rio"],

            continuity_uid=
                continuity_uid,

            rig_id=identity["rig"],

            current_riv_id=
                identity["riv"],

            trust_tier="T2",

            corridor=corridor,

            identity_state="ACTIVE"
        )

        session.add(rio)

        # --------------------------------
        # USER PROJECTION
        # Public-facing continuity surface
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
                full_name,

            national_id=
                national_id,

            kyc_status=
                "VERIFIED"
        )

        session.add(user)

        session.commit()

        print(
            f"✅ Continuity onboarded: "
            f"{identity['railone_id']}"
        )

        return {

            "created": True,

            "railone_id":
                identity["railone_id"],

            "continuity_uid":
                continuity_uid,

            "rig":
                identity["rig"],

            "rio":
                identity["rio"],

            "riv":
                identity["riv"],

            "kyc_status":
                "VERIFIED"
        }

    finally:

        session.close()

# --------------------------------
# GET USER BY NATIONAL ID
# --------------------------------
def get_user_by_national_id(national_id):

    session = SessionLocal()

    try:
        user = session.query(User).filter_by(national_id=national_id).first()

        if not user:
            return None

        return {
            "railone_id": user.railone_id,
            "national_id": user.national_id,
            "full_name": user.full_name,
            "kyc_status": user.kyc_status
        }

    finally:
        session.close()


# --------------------------------
# GET USER BY RAILONE ID
# --------------------------------
def get_user_by_railone_id(railone_id):

    session = SessionLocal()

    try:
        user = session.query(User).filter_by(railone_id=railone_id).first()

        if not user:
            return None

        return {
            "railone_id": user.railone_id,
            "national_id": user.national_id,
            "full_name": user.full_name,
            "kyc_status": user.kyc_status
        }

    finally:
        session.close()


# --------------------------------
# LIST USERS
# --------------------------------
def list_users():

    session = SessionLocal()

    try:
        users = session.query(User).all()

        return [
            {
                "railone_id": u.railone_id,
                "national_id": u.national_id,
                "full_name": u.full_name,
                "kyc_status": u.kyc_status
            }
            for u in users
        ]

    finally:
        session.close()


# --------------------------------
# SAFE ENSURE USER (UTILITY)
# --------------------------------
def ensure_user(full_name: str, national_id: str):
    """
    Creates user if not exists, otherwise returns existing.
    """
    user = get_user_by_national_id(national_id)

    if user:
        return user

    return create_user(full_name, national_id)