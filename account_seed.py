# ==============================
# account_seed.py
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
            ("MPESA", "KES", 350000),
            ("BANK_KE", "KES", 600000),
            ("BANK_UG", "UGX", 600000),
            ("BANK_TZ", "TZS", 700000),
            ("SMOVE", "KES", 700000),
            ("SMOVE", "USD", 100000),
            ("SMOVE", "TZS", 300000),
        ]

        for inst, ccy, balance in accounts:
            acc_id = f"{inst}-{railone_id}-{ccy}"

            acc = Account(
                id=acc_id,
                currency=ccy,
                account_type=inst,
                balance=float(balance),
                locked_balance=0.0
            )

            session.add(acc)

        session.commit()

    finally:
        session.close()