# ==============================
# seed_network_users.py
# ==============================

from user_service import onboard_user
from network_seed import seed_all
from ledger.db import SessionLocal
from ledger.models import Account
from ledger.models import UserAccountLink


def seed_users_per_institution():

    session = SessionLocal()

    try:
        users = [
            # PSP_KE users
            ("Faith KE", "20000101", "PSP_KE", "KES"),
            ("Brian KE", "20000102", "PSP_KE", "KES"),
            ("Amina KE", "20000103", "PSP_KE", "KES"),

            # BANK_TZ users
            ("John TZ", "30000101", "BANK_TZ", "TZS"),
            ("Neema TZ", "30000102", "BANK_TZ", "TZS"),
            ("Kelvin TZ", "30000103", "BANK_TZ", "TZS"),

            # PSP_UG users
            ("Peter UG", "40000101", "PSP_UG", "UGX"),
            ("Grace UG", "40000102", "PSP_UG", "UGX"),
            ("Daniel UG", "40000103", "PSP_UG", "UGX"),
        ]

        for name, national_id, inst, currency in users:

            railone_id = onboard_user(name, national_id)

            # seed institutions + keys + links
            seed_all(railone_id)

            # --------------------------------
            # CREATE ACCOUNT (MIRROR)
            # --------------------------------
            acc_id = f"{inst}-{railone_id}-{currency}"

            existing = session.query(Account).filter_by(id=acc_id).first()

            if not existing:
                acc = Account(
                    id=acc_id,
                    currency=currency,
                    account_type="EXTERNAL_MIRROR",
                    balance=500000.0,   # demo liquidity
                    locked_balance=0.0
                )
                session.add(acc)

        session.commit()
        print("✅ Network users seeded successfully")

    finally:
        session.close()