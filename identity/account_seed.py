# ==============================
# identity/account_seed.py
# RailOne Continuity Account Seed
# ==============================

from ledger.db import SessionLocal

from ledger.models import Account


# ==========================================
# SEED USER EXECUTION ACCOUNTS
# ==========================================
def seed_user_accounts(

    railone_id,

    continuity_uid=None
):

    session = SessionLocal()

    try:

        # --------------------------------
        # EXISTING ACCOUNT CHECK
        # --------------------------------
        existing = (

            session.query(Account)

            .filter(
                Account.id.contains(railone_id)
            )

            .first()
        )

        if existing:

            print(
                f"⚠️ Accounts already exist "
                f"for {railone_id}"
            )

            return

        # --------------------------------
        # EXECUTION SURFACES
        # --------------------------------
        accounts = [

            # Kenya
            ("MPESA", "KES"),

            ("BANK_KE", "KES"),

            # Uganda
            ("BANK_UG", "UGX"),

            # Tanzania
            ("BANK_TZ", "TZS"),

            # RailOne Internal FX Rails
            ("SMOVE", "KES"),

            ("SMOVE", "USD"),

            ("SMOVE", "TZS"),
        ]

        for institution, currency in accounts:

            account_id = (
                f"{institution}-"
                f"{railone_id}-"
                f"{currency}"
            )

            account = Account(

                # --------------------------------
                # EXECUTION ACCOUNT ID
                # --------------------------------
                id=account_id,

                # --------------------------------
                # CONTINUITY REFERENCES
                # --------------------------------
                railone_id=railone_id,

                continuity_uid=continuity_uid,

                # --------------------------------
                # ACCOUNT CONTEXT
                # --------------------------------
                institution_id=institution,

                currency=currency,

                account_type=
                    "EXTERNAL_MIRROR",

                # --------------------------------
                # SIMULATED EXTERNAL LIQUIDITY
                # --------------------------------
                mirrored_available_state=
                    500000.0,

                execution_reservation=
                    0.0
            )

            session.add(account)

        session.commit()

        print(
            f"✅ Execution accounts seeded "
            f"for {railone_id}"
        )

    finally:

        session.close()