from ledger.db import SessionLocal

from ledger.models import Account


# =========================================
# ENSURE EXECUTION ACCOUNT EXISTS
# =========================================
def ensure_execution_account_exists(
    account_id,
    railone_id,
    continuity_uid,
    institution_id,
    currency,
    account_type="EXECUTION_SURFACE",
    mirrored_available_state=0.0
):

    session = SessionLocal()

    try:

        existing = (
            session.query(Account)
            .filter_by(id=account_id)
            .first()
        )

        if existing:
            return existing

        account = Account(
            id=account_id,
            railone_id=railone_id,
            continuity_uid=continuity_uid,
            institution_id=institution_id,
            currency=currency,
            account_type=account_type,
            mirrored_available_state=mirrored_available_state,
            execution_reservation=0.0
        )

        session.add(account)

        session.commit()

        return account

    finally:

        session.close()