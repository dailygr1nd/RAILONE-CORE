# ==============================
# user_directory.py (FULLY FIXED)
# ==============================

from ledger.db import SessionLocal
from identity.models import User
from identity.identity_engine import generate_railone_id


# --------------------------------
# CREATE USER (CORE)
# --------------------------------
def create_user(full_name: str, national_id: str):

    session = SessionLocal()

    try:
        # 🔒 prevent duplicates
        existing = session.query(User).filter_by(national_id=national_id).first()

        if existing:
            return {
                "railone_id": existing.railone_id,
                "national_id": existing.national_id,
                "kyc_status": existing.kyc_status,
                "created": False
            }

        from identity.identity_engine import generate_railone_id

        identity = generate_railone_id(
            corridor="EA",
            trust_tier="T2",
            revision=1
        )

        railone_id = identity["railone_id"]

        user = User(
            railone_id=railone_id,
            full_name=full_name,
            national_id=national_id,
            kyc_status="VERIFIED"
        )

        session.add(user)
        session.commit()

        return {
            "railone_id": railone_id,
            "national_id": national_id,
            "kyc_status": "VERIFIED",
            "created": True
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