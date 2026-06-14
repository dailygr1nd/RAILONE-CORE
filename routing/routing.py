# ==============================
# routing.py
# RailOne Routing Core
# ==============================

from routing.routing_brain import (
    compute_rail_health
)

from routing.routescoring import (
    score_route
)

from liquidity_engine import (
    check_liquidity
)


# --------------------------------
# RAIL CLASSIFICATION
# --------------------------------
def classify_rail(account_id: str) -> str:

    if account_id.startswith("BANK_KE"):
        return "BANK_KE"

    if account_id.startswith("BANK_TZ"):
        return "BANK_TZ"

    if account_id.startswith("BANK_UG"):
        return "BANK_UG"

    if account_id.startswith("MPESA"):
        return "MPESA"

    if account_id.startswith("SMOVE"):
        return "SMOVE"

    return "UNKNOWN"


# --------------------------------
# ROUTE OBJECT
# --------------------------------
def build_route_object(

    rail: str,

    amount: float,

    score: float = 0,

    health: float = 0
):

    return {

        "rail":
            rail,

        "type":
            rail,

        "cost":
            round(
                amount * 0.001,
                6
            ),

        "score":
            score,

        "health":
            health
    }


# --------------------------------
# RANK ROUTES
# --------------------------------
def rank_routes(

    candidate_rails,

    amount,

    currency,

    cross_border=False
):

    ranked_routes = []

    for rail in candidate_rails:

        # ----------------------------
        # HARD FILTER
        # ----------------------------
        has_liquidity, available = (

            check_liquidity(

                route_type=rail,

                currency=currency,

                amount=amount
            )
        )

        if not has_liquidity:

            continue

        # ----------------------------
        # HEALTH
        # ----------------------------
        health_score = (

            compute_rail_health(
                rail
            )
        )

        # ----------------------------
        # ROUTE SCORE
        # ----------------------------
        route_obj = {

            "type":
                rail
        }

        route_score = score_route(

            route=route_obj,

            amount=amount,

            available_mirrored_available_state=
                available
        )

        if cross_border and rail == "SMOVE":

            route_score += 2

        total_score = (

            health_score
            +
            route_score
        )

        ranked_routes.append(

            build_route_object(

                rail=rail,

                amount=amount,

                score=round(
                    total_score,
                    4
                ),

                health=round(
                    health_score,
                    4
                )
            )
        )

    ranked_routes.sort(

        key=lambda x:
            x["score"],

        reverse=True
    )

    return ranked_routes


# --------------------------------
# BACKWARDS COMPATIBILITY
# --------------------------------
def get_best_rail(

    candidate_rails,

    amount,

    currency,

    cross_border=False
):

    ranked = rank_routes(

        candidate_rails,

        amount,

        currency,

        cross_border
    )

    if not ranked:

        return {

            "rail":
                "SMOVE",

            "type":
                "SMOVE",

            "cost":
                round(
                    amount * 0.001,
                    6
                ),

            "score":
                0,

            "health":
                0
        }

    return ranked[0]