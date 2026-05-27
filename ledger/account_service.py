from ledger.db import SessionLocal

from ledger.models import Account

from execution.event_store import emit_event


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

    mirrored_available_state=0.0,

    adapter_type=None,

    external_account_reference=None,

    provider_metadata=None
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

            institution_id=(
                institution_id
            ),

            adapter_type=adapter_type,

            currency=currency,

            account_type=account_type,

            mirrored_available_state=(
                mirrored_available_state
            ),

            execution_reservation=0.0,

            execution_capacity=(
                mirrored_available_state
            ),

            external_account_reference=(
                external_account_reference
            ),

            provider_metadata=(
                provider_metadata
            )
        )

        session.add(account)

        session.commit()

        emit_event(

            continuity_uid=(
                continuity_uid
            ),

            event_type=(
                "EXECUTION_SURFACE_CREATED"
            ),

            payload={

                "account_id":
                    account_id,

                "institution_id":
                    institution_id,

                "currency":
                    currency,

                "adapter_type":
                    adapter_type
            }
        )

        return account

    finally:

        session.close()