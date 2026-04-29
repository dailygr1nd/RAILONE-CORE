# routing.py

from routing_brain import compute_rail_health
from routescoring import score_route
from liquidity_engine import check_liquidity


def classify_rail(account_id):
    if account_id.startswith("BANK_KE"):
        return "BANK_KE"
    if account_id.startswith("BANK_TZ"):
        return "BANK_TZ"
    if account_id.startswith("BANK_UG"):
        return "BANK_UG"

    if account_id.startswith("PSP_MPESA_KE") or account_id.startswith("PSP_AIRTEL_KE"):
        return "PSP_KE"

    if account_id.startswith("PSP_MPESA_TZ") or account_id.startswith("PSP_AIRTEL_TZ"):
        return "PSP_TZ"

    if account_id.startswith("PSP_AIRTEL_UG"):
        return "PSP_UG"

    if account_id.startswith("SMOVE"):
        return "SMOVE"

    return "UNKNOWN"


# --------------------------------
# 🔥 SMART ROUTING
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
            continue  # 🚫 cannot use this rail

        # --------------------------------
        # HEALTH SCORE
        # --------------------------------
        health_score = compute_rail_health(rail)

        # --------------------------------
        # FINAL SCORING
        # --------------------------------
        route_obj = {"type": rail}

        final_score = score_route(
            route=route_obj,
            amount=amount,
            available_balance=1_000_000  # liquidity already checked
        )

        # cross-border bias
        if cross_border and rail == "SMOVE":
            final_score += 2

        # combine intelligence + scoring
        total_score = health_score + final_score

        if total_score > best_score:
            best_score = total_score
            best = rail

    return best or "SMOVE"  # fallback

def build_route(sender_rail, receiver_rail, amount, currency):

    # direct route possible
    if sender_rail != receiver_rail:
        return [sender_rail, "SMOVE", receiver_rail]

    # cross-border KE → TZ via UG
    if sender_rail == "PSP_KE" and receiver_rail == "BANK_TZ":
        return ["PSP_KE", "PSP_UG", "BANK_TZ"]

    # fallback: use best rail as bridge
    bridge = get_best_rail(
        candidate_rails=["PSP_UG", "SMOVE"],
        amount=amount,
        currency=currency,
        cross_border=True
    )

    return [sender_rail, bridge, receiver_rail]

def execute_route(tx, router, attestation_engine):

    route = build_route(
        tx.payload["sender"]["institution"],
        tx.payload["receiver"]["institution"],
        tx.payload["amount"]["value"],
        tx.payload["amount"]["currency"]
    )
    tx.append_chain(f"HOP:{route[i-1]}->{inst}")

    current_amount = tx.payload["amount"]["value"]

    for i in range(len(route)):

        inst = route[i]

        # -----------------------------
        # FIRST HOP (VERIFY + RESERVE)
        # -----------------------------
        if i == 0:

            res = router.call(inst, "verify_funds", "user_ke", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "FUNDS_AVAILABLE",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "FUNDS_AVAILABLE", res["attestation"])

            res = router.call(inst, "reserve_funds", "user_ke", current_amount)

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
            current_amount = int(current_amount * 1.8)

        # -----------------------------
        # FINAL RECEIVER
        # -----------------------------
        else:

            res = router.call(inst, "receive_funds", "user_tz", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "SETTLED",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "SETTLED", res["attestation"])

    return route