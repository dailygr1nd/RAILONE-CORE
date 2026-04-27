# ==============================
# route_planner.py
# ==============================

def get_route(sender_inst, receiver_inst):

    # simple hardcoded for now
    if sender_inst == "PSP_KE" and receiver_inst == "BANK_TZ":
        return ["PSP_KE", "PSP_UG", "BANK_TZ"]

    return [sender_inst, receiver_inst]

from attestation_engine import AttestationEngine
from route_planner import get_route


def execute_multi_hop(tx, router):

    attestation_engine = AttestationEngine()

    route = get_route(
        tx.payload["sender"]["institution"],
        tx.payload["receiver"]["institution"]
    )

    amount = tx.payload["amount"]["value"]
    current_amount = amount

    for i in range(len(route)):

        inst = route[i]

        # -----------------------------
        # VERIFY FUNDS (FIRST NODE ONLY)
        # -----------------------------
        if i == 0:
            res = router.call(inst, "verify_funds", "user_ke", current_amount)

            if res["status"] != "OK":
                raise Exception("FUNDS_NOT_AVAILABLE")

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

            res = router.call(inst, "receive_funds", "intermediate", current_amount)

            attestation_engine.verify(
                tx.payload_hash,
                "SETTLED",
                res["attestation"],
                inst
            )

            tx.add_attestation(inst, "SETTLED", res["attestation"])

            # simulate FX conversion
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