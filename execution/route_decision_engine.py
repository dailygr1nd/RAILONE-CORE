# ==========================================
# execution/route_decision_engine.py
# ==========================================

from ledger.db import SessionLocal

from execution.route_decision_models import (
    RouteDecision
)


def record_route_decision(

    utt_id,
    rtt_id,
    route,
    rank_position
):

    session = SessionLocal()

    try:

        decision = RouteDecision(

            utt_id=utt_id,

            rtt_id=rtt_id,

            rail=route["rail"],

            score=route["score"],

            rank_position=str(
                rank_position
            ),

            rationale={

                "success_rate":
                    route.get(
                        "success_rate"
                    ),

                "latency":
                    route.get(
                        "latency"
                    ),

                "health":
                    route.get(
                        "health"
                    )
            }
        )

        session.add(decision)

        session.commit()

    finally:

        session.close()