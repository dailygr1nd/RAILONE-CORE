# ==========================================
# execution/reconciliation_engine.py
# ==========================================

from ledger.db import SessionLocal

from execution.reconciliation_models import (
    ReconciliationRecord
)


def record_reconciliation(

    utt_id,
    rtt_id,
    provider,
    provider_reference
):

    session = SessionLocal()

    try:

        record = ReconciliationRecord(

            utt_id=
                utt_id,

            rtt_id=
                rtt_id,

            provider=
                provider,

            provider_reference=
                provider_reference,

            reconciled=
                False
        )

        session.add(record)

        session.commit()

    finally:

        session.close()