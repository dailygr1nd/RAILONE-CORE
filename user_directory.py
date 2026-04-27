# ==============================
# user_directory.py
# ==============================

from ledger.db import SessionLocal
from ledger.models import User


def list_users():

    session = SessionLocal()

    try:
        users = session.query(User).all()

        return [
            {
                "railone_id": u.railone_id,
                "national_id": u.national_id,
                "kyc_status": u.kyc_status
            }
            for u in users
        ]

    finally:
        session.close()


def get_user_by_national_id(national_id):

    session = SessionLocal()

    try:
        user = session.query(User).filter_by(national_id=national_id).first()

        if not user:
            return None

        return {
            "railone_id": user.railone_id,
            "national_id": user.national_id
        }

    finally:
        session.close()