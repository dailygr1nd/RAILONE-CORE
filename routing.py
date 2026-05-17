# ==============================
# routing.py (PROTOCOL READY)
# ==============================

from routing_brain import compute_rail_health
from routescoring import score_route
from liquidity_engine import check_liquidity


# --------------------------------
# 🔐 RAIL CLASSIFICATION
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
# 🔐 ROUTE OBJECT BUILDER
# --------------------------------
def build_route_object(rail: str, amount: float) -> dict:
    """
    Canonical route schema used across:
    - quote_engine
    - tx_verifier
    - execution_engine
    """

    return {
        "type": rail,
        "rail": rail,
        "cost": round(amount * 0.001, 6),  # simple deterministic cost model
    }


# --------------------------------
# 🔥 SMART RAIL SELECTION
# --------------------------------
def get_best_rail(candidate_rails, amount, currency, cross_border=False):

    best = None
    best_score = -999

    for rail in candidate_rails:

        # --------------------------------
        # LIQUIDITY CHECK (HARD FILTER)
        # --------------------------------
        has_liquidity, _ = check_liquidity(
            route_type=rail,
            currency=currency,
            amount=amount
        )

        if not has_liquidity:
            continue

        # --------------------------------
        # HEALTH
        # --------------------------------
        health_score = compute_rail_health(rail)

        # --------------------------------
        # SCORING
        # --------------------------------
        route_obj = {"type": rail}

        score = score_route(
            route=route_obj,
            amount=amount,
            available_mirrored_available_state=1_000_000
        )

        # Cross-border bias
        if cross_border and rail == "SMOVE":
            score += 2

        total_score = health_score + score

        if total_score > best_score:
            best_score = total_score
            best = rail

    # --------------------------------
    # FALLBACK
    # --------------------------------
    if not best:
        best = "SMOVE"

    return build_route_object(best, amount)


# --------------------------------
# 🌍 ROUTE SCHEME (MULTI-HOP LOGIC)
# --------------------------------
def build_route(sender_rail, receiver_rail, amount, currency):

    """
    Returns a LIST of route objects
    """

    # --------------------------------
    # SAME RAIL (DIRECT)
    # --------------------------------
    if sender_rail == receiver_rail:
        return [build_route_object(sender_rail, amount)]

    # --------------------------------
    # DIRECT BANK → BANK (same region)
    # --------------------------------
    if sender_rail.startswith("BANK") and receiver_rail.startswith("BANK"):
        return [
            build_route_object(sender_rail, amount),
            build_route_object(receiver_rail, amount)
        ]

    # --------------------------------
    # DEFAULT CROSS-BORDER VIA CORE (SMOVE)
    # --------------------------------
    return [
        build_route_object(sender_rail, amount),
        build_route_object("SMOVE", amount),
        build_route_object(receiver_rail, amount)
    ]


# --------------------------------
# 🚀 EXECUTION ROUTE (ATTESTATION FLOW)
# --------------------------------
def execute_route(tx, router, attestation_engine):

    route = build_route(
        tx.payload["sender"]["institution"],
        tx.payload["receiver"]["institution"],
        tx.payload["amount"]["value"],
        tx.payload["amount"]["currency"]
    )

    current_amount = tx.payload["amount"]["value"]

    for i in range(len(route)):

        inst = route[i]["type"]

        # -----------------------------
        # FIRST HOP
        # -----------------------------
        if i == 0:

            res = router.call(inst, "verify_funds", "user", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "FUNDS_AVAILABLE",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "FUNDS_AVAILABLE", res["attestation"])

            res = router.call(inst, "reserve_funds", "user", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "FUNDS_RESERVED",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "FUNDS_RESERVED", res["attestation"])

        # -----------------------------
        # INTERMEDIATE HOP
        # -----------------------------
        elif i < len(route) - 1:

            res = router.call(inst, "receive_funds", "bridge", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "SETTLED",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "SETTLED", res["attestation"])

            # FX simulation
            current_amount = int(current_amount * 1.01)

        # -----------------------------
        # FINAL RECEIVER
        # -----------------------------
        else:

            res = router.call(inst, "receive_funds", "user", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "SETTLED",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "SETTLED", res["attestation"])

    return route