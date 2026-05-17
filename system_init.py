# ==============================
# system_init.py
# ==============================

from ledger.db import engine, SessionLocal
from ledger.models import Base, Account
from ledger.ledger_service import apply_genesis


def init_system():

    print("🚀 Initializing system...")

    # -----------------------------
    # CREATE TABLES
    # -----------------------------
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:
        # -----------------------------
        # CHECK IF ACCOUNTS EXIST
        # -----------------------------
        existing = session.query(Account).first()

        if existing:
            print("✅ System already initialized")
            return

        print("🔧 Seeding accounts...")

        users = ["10000891", "10000555"]

        rails = [
            ("MPESA", "KES"),
            ("BANK_KE", "KES"),
            ("BANK_UG", "UGX"),
            ("BANK_TZ", "TZS"),
            ("SMOVE", "KES"),
            ("SMOVE", "USD"),
            ("SMOVE", "TZS"),
        ]

        for user in users:
            for inst, ccy in rails:
                acc_id = f"{inst}-{user}-{ccy}"

                acc = Account(
                    id=acc_id,
                    currency=ccy,
                    account_type="USER",
                    mirrored_available_state=0.0,
                    execution_reservation=0.0,
                    allow_overdraft="false"
                )

                session.add(acc)
                session.commit()

                # GENESIS FUNDING
                apply_genesis(session, acc_id, 100000)

        session.commit()

        print("✅ Accounts seeded & funded")

    finally:
        session.close()