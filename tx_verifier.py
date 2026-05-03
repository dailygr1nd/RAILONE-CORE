# ==============================
# tx_verifier.py (FINAL)
# ==============================

import json
import hashlib

from token_factory import TokenFactory


# --------------------------------
# ROUTE HASH
# --------------------------------
def compute_route_hash(route, rtt):

    route_str = json.dumps({
        "type": route.get("type"),
        "rail": route.get("rail"),
        "cost": round(route.get("cost", 0), 6)
    }, sort_keys=True)

    return hashlib.sha256(
        f"{route_str}|{rtt}".encode()
    ).hexdigest()


# --------------------------------
# VERIFY
# --------------------------------
def verify_transaction(tx: dict, institution_id="R1CORE"):

    result = {"valid": True, "checks": []}

    def fail(reason):
        result["valid"] = False
        result["checks"].append({"status": "FAIL", "reason": reason})

    def ok(msg):
        result["checks"].append({"status": "OK", "msg": msg})

    try:
        # --------------------------------
        # ETK CHECK
        # --------------------------------
        if not tx.get("etk_s"):
            fail("ETK-S missing")
        else:
            ok("ETK-S present")

        if not tx.get("etk_r"):
            fail("ETK-R missing")
        else:
            ok("ETK-R present")

        # --------------------------------
        # RTT VERIFY
        # --------------------------------
        payload = tx.get("payload_rtt")
        sig_hex = tx.get("rtt_signature")

        if not payload or not sig_hex:
            fail("RTT payload/signature missing")
        else:
            sig = bytes.fromhex(sig_hex)

            if not TokenFactory.verify(payload, sig, institution_id):
                fail("RTT signature invalid")
            else:
                ok("RTT signature valid")

            expected_rtt = TokenFactory._hash(payload)

            if expected_rtt != tx.get("rtt"):
                fail("RTT hash mismatch")
            else:
                ok("RTT hash valid")

        # --------------------------------
        # ROUTE BINDING
        # --------------------------------
        if tx.get("route_result"):
            expected = compute_route_hash(
                tx["route_result"],
                tx["rtt"]
            )

            if expected != tx.get("route_hash"):
                fail("Route tampering detected")
            else:
                ok("Route binding valid")

        # --------------------------------
        # UTT
        # --------------------------------
        if tx.get("utt"):
            ok("UTT present")
        else:
            result["checks"].append({
                "status": "INFO",
                "msg": "UTT not yet assigned"
            })

        return result

    except Exception as e:
        return {"valid": False, "error": str(e)}