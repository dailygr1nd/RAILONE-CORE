# ==============================
# user_service.py (FINAL FIXED)
# ==============================

from ledger.db import SessionLocal
from identity.models import User

from identity.identity_engine import generate_railone_id


# --------------------------------
# ONBOARD USER (IDEMPOTENT)
# --------------------------------
def onboard_user(name, national_id):

    session = SessionLocal()

    existing_identity = (

    session.query(User)

    .filter_by(
        national_id=national_id
    )

    .first()
)

    session = SessionLocal()

    try:
        # 🔥 reuse existing user
        existing = session.query(User).filter_by(
            national_id=national_id
        ).first()

        if existing:
            return existing.railone_id

        # 🔥 create new
        identity = generate_railone_id(
        corridor="EA",
        trust_tier="T2",
        revision=1
        )

        railone_id = identity["railone_id"]

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