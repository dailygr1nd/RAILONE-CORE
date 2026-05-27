# ==========================================
# ledger/bootstrap.py
# RailOne Execution Bootstrap
# ==========================================

from ledger.db import SessionLocal

from ledger.models import (
    Institution
)


def bootstrap_institutions():

    session = SessionLocal()

    try:

        institutions = [

            Institution(

                institution_id="MPESA",

                institution_name="M-PESA",

                institution_type=(
                    "MOBILE_MONEY"
                ),

                country="KE",

                supported_adapters=[
                    "mpesa"
                ],

                supported_currencies=[
                    "KES"
                ],

                replay_policy={

                    "max_retries": 3,

                    "requires_reconciliation":
                        True
                },

                execution_policy={

                    "settlement_model":
                        "ASYNC"
                },

                attestation_capable=False
            ),

            Institution(

                institution_id="BANK_KE",

                institution_name=(
                    "Kenyan Bank Node"
                ),

                institution_type="BANK",

                country="KE",

                supported_adapters=[
                    "flutterwave",
                    "paystack"
                ],

                supported_currencies=[
                    "KES"
                ],

                replay_policy={

                    "max_retries": 2
                },

                execution_policy={

                    "settlement_model":
                        "SYNC"
                },

                attestation_capable=True
            )
        ]

        for institution in institutions:

            existing = (

                session.query(Institution)

                .filter(
                    Institution.institution_id
                    == institution.institution_id
                )

                .first()
            )

            if not existing:

                session.add(institution)

        session.commit()

        print(
            "✅ Institutions bootstrapped"
        )

    finally:

        session.close()