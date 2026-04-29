# ==============================
# user_service.py (FINAL FIXED)
# ==============================

from ledger.db import SessionLocal
from ledger.models import User

from identity_db import lookup_identity
from identity_engine import generate_railone_id


# --------------------------------
# ONBOARD USER (IDEMPOTENT)
# --------------------------------
def onboard_user(name, national_id):

    record = lookup_identity(national_id, name)

    if record is None:
        raise Exception("INVALID_IDENTITY")

    if record == "NAME_MISMATCH":
        raise Exception("NAME_MISMATCH")

    session = SessionLocal()

    try:
        # 🔥 reuse existing user
        existing = session.query(User).filter_by(
            national_id=national_id
        ).first()

        if existing:
            return existing.railone_id

        # 🔥 create new
        railone_id = generate_railone_id()

        user = User(
            railone_id=railone_id,
            national_id=national_id,
            kyc_status="VERIFIED"
        )

        session.add(user)
        session.commit()

        return railone_id

    finally:
        session.close()


# --------------------------------
# LOOKUP USER BY NATIONAL ID
# --------------------------------
def get_railone_id_by_national_id(national_id):

    session = SessionLocal()

    try:
        user = session.query(User).filter_by(
            national_id=national_id
        ).first()

        if not user:
            return None

        return user.railone_id

    finally:
        session.close()