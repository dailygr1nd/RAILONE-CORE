# ==============================
# routing/execution_plan_engine.py
# RailOne Execution Plan Engine
# ==============================

from ledger.db import SessionLocal

from routing.models.execution_plan_models import (
    ExecutionPlanRecord
)


def save_execution_plan(

    utt_id,
    continuity_uid,
    routes,
    max_attempts=5
):

    session = SessionLocal()

    try:

        plan = ExecutionPlanRecord(

            utt_id=utt_id,

            continuity_uid=
                continuity_uid,

            ranked_routes=
                routes,

            max_attempts=
                max_attempts,

            attempts_used=0,

            failed_routes=[]
        )

        session.add(plan)

        session.commit()

        return plan

    finally:

        session.close()


def load_execution_plan(utt_id):

    session = SessionLocal()

    try:

        return (

            session.query(
                ExecutionPlanRecord
            )

            .filter_by(
                utt_id=utt_id
            )

            .first()
        )

    finally:

        session.close()