# ==========================================
# routing/execution_plan_repository.py
# RailOne Execution Plan Repository
# ==========================================

from ledger.db import SessionLocal

from routing.models.execution_plan_models import (
    ExecutionPlanModel
)


class ExecutionPlanRepository:

    @staticmethod
    def save(plan):

        session = SessionLocal()

        try:

            model = ExecutionPlanModel(

                utt_id=plan.utt_id,

                routes=plan.to_dict()["routes"],

                max_attempts=plan.max_attempts,

                attempts_used=plan.attempts_used
            )

            session.add(model)

            session.commit()

            return model.id

        finally:

            session.close()

    @staticmethod
    def get(utt_id):

        session = SessionLocal()

        try:

            return (

                session.query(
                    ExecutionPlanModel
                )

                .filter_by(
                    utt_id=utt_id
                )

                .first()
            )

        finally:

            session.close()

    @staticmethod
    def increment_attempt(utt_id):

        session = SessionLocal()

        try:

            plan = (

                session.query(
                    ExecutionPlanModel
                )

                .filter_by(
                    utt_id=utt_id
                )

                .first()
            )

            if not plan:
                return

            plan.attempts_used += 1

            session.commit()

        finally:

            session.close()

    @staticmethod
    def mark_success(

        utt_id,
        successful_route
    ):

        session = SessionLocal()

        try:

            plan = (

                session.query(
                    ExecutionPlanModel
                )

                .filter_by(
                    utt_id=utt_id
                )

                .first()
            )

            if not plan:
                return

            plan.successful_route = (
                successful_route
            )

            session.commit()

        finally:

            session.close()

    @staticmethod
    def update_routes(

        utt_id,
        routes
    ):

        session = SessionLocal()

        try:

            plan = (

                session.query(
                    ExecutionPlanModel
                )

                .filter_by(
                    utt_id=utt_id
                )

                .first()
            )

            if not plan:
                return

            plan.routes = routes

            session.commit()

        finally:

            session.close()