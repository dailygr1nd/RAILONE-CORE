# ==============================
# user_service.py
# ==============================

from ledger.db import SessionLocal
from ledger.models import User
from identity_engine import generate_railone_id


def onboard_user(name, national_id):

    session = SessionLocal()

    try:
        existing = session.query(User).filter_by(national_id=national_id).first()

        if existing:
            return existing.railone_id

        railone_id = generate_railone_id()

        user = User(
            railone_id=railone_id,
            username=None,
            national_id=national_id,
            kyc_status="VERIFIED"
        )

        session.add(user)
        session.commit()

        return railone_id

    finally:
        session.close()

def get_railone_id_by_national_id(national_id):

    session = SessionLocal()

    try:
        user = session.query(User).filter_by(national_id=national_id).first()

        if not user:
            return None

        return user.railone_id

    finally:
        session.close()