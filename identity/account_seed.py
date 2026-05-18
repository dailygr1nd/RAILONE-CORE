# ==============================
# account_seed.py (REFACTORED)
# ==============================

from ledger.db import SessionLocal
from ledger.models import Account


def seed_user_accounts(railone_id):

    

    session = SessionLocal()

    try:
        existing = session.query(Account).filter(
            Account.id.contains(railone_id)
        ).first()

        if existing:
            return

        accounts = [
            ("MPESA", "KES"),
            ("BANK_KE", "KES"),
            ("BANK_UG", "UGX"),
            ("BANK_TZ", "TZS"),
            ("SMOVE", "KES"),
            ("SMOVE", "USD"),
            ("SMOVE", "TZS"),
        ]

        for inst, ccy in accounts:
            acc_id = f"{inst}-{railone_id}-{ccy}"

            acc = Account(
    id=acc_id,
    currency=ccy,
    account_type="EXTERNAL_MIRROR",

    # 🔥 simulate external funds (non-custodial mirror)
    mirrored_available_state=500000.0,
    execution_reservation=0.0
)

            session.add(acc)

        session.commit()

    finally:
        session.close()