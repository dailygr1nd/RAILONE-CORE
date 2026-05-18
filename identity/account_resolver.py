# ==============================
# account_resolver.py
# ==============================

from identity.models import UserAccountLink
from ledger.db import SessionLocal


def get_user_account(railone_id, institution_id):

    session = SessionLocal()

    try:
        link = session.query(UserAccountLink).filter_by(
            railone_id=railone_id,
            institution_id=institution_id
        ).first()

        if not link:
            return None

        return {
            "institution": institution_id,
            "account": link.external_account_ref,
            "currency": link.currency
        }

    finally:
        session.close()