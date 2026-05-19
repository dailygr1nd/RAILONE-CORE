# ==============================
# identity/account_resolver.py
# RailOne Continuity Account Resolver
# ==============================

from ledger.db import SessionLocal

from ledger.models import (
    UserAccountLink
)


# ==========================================
# RESOLVE USER EXECUTION ACCOUNT
# ==========================================
def get_user_account(

    railone_id,

    institution_id
):

    session = SessionLocal()

    try:

        link = (

            session.query(UserAccountLink)

            .filter_by(

                railone_id=railone_id,

                institution_id=institution_id
            )

            .first()
        )

        if not link:

            return None

        return {

            # --------------------------------
            # CONTINUITY CONTEXT
            # --------------------------------
            "railone_id":
                link.railone_id,

            # --------------------------------
            # EXECUTION SURFACE
            # --------------------------------
            "institution":
                institution_id,

            "external_account":
                link.external_account_ref,

            "currency":
                link.currency,

            # --------------------------------
            # REPLAY-SAFE RESOLUTION
            # --------------------------------
            "resolution_state":
                "ACTIVE"
        }

    finally:

        session.close()