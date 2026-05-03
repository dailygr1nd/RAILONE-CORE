# ==============================
# tx_verifier.py (FINAL — PRODUCTION SAFE)
# ==============================

import json
import hashlib

from token_factory import TokenFactory


# --------------------------------
# 🔐 ROUTE NORMALIZATION
# --------------------------------
def normalize_route(route: dict) -> dict:
    return {
        "type": route.get("type"),
        "rail": route.get("rail"),
        "cost": round(route.get("cost", 0), 6),
    }


# --------------------------------
# 🔐 ROUTE HASH
# --------------------------------
def compute_route_hash(route, rtt):
    normalized = normalize_route(route)
    route_str = json.dumps(normalized, sort_keys=True)

    return hashlib.sha256(
        f"{route_str}|{rtt}".encode()
    ).hexdigest()


# --------------------------------
# MAIN VERIFIER
# --------------------------------
def verify_transaction(tx: dict, institution_id="R1CORE") -> dict:

    result = {
        "valid": True,
        "checks": []
    }

    def fail(reason):
        result["valid"] = False
        result["checks"].append({
            "status": "FAIL",
            "reason": reason
        })

    def ok(msg):
        result["checks"].append({
            "status": "OK",
            "msg": msg
        })

    try:
        # --------------------------------
        # 1. ETK-S
        # --------------------------------
        if not tx.get("etk_s"):
            fail("ETK-S missing")
        else:
            ok("ETK-S present")

        # --------------------------------
        # 2. ETK-R
        # --------------------------------
        if not tx.get("etk_r"):
            fail("ETK-R missing")
        else:
            ok("ETK-R present")

        # --------------------------------
        # 3. RTT SIGNATURE + STRUCTURE
        # --------------------------------
        payload_rtt = tx.get("payload_rtt")
        sig_rtt_hex = tx.get("rtt_signature")

        if not payload_rtt or not sig_rtt_hex:
            fail("RTT payload/signature missing")
        else:
            try:
                signature = bytes.fromhex(sig_rtt_hex)
            except Exception:
                fail("RTT signature invalid format")
                signature = None

            if signature:
                # 🔐 SIGNATURE VERIFY
                if not TokenFactory.verify(payload_rtt, signature, institution_id):
                    fail("RTT signature invalid")
                else:
                    ok("RTT signature valid")

                # --------------------------------
                # RTT STRUCTURE (QUOTE + PRICING BOUND)
                # --------------------------------
                parts = payload_rtt.split("|")

                if len(parts) != 6:
                    fail("RTT format invalid (quote/pricing not bound)")
                else:
                    _, etk_s, etk_r, tx_id, pricing_hash, quote_id = parts

                    # --------------------------------
                    # QUOTE BINDING
                    # --------------------------------
                    if quote_id != tx.get("quote_id"):
                        fail("Quote ID mismatch")
                    else:
                        ok("Quote binding valid")

                    # --------------------------------
                    # PRICING BINDING
                    # --------------------------------
                    pricing = tx.get("pricing", {})

                    pricing_str = json.dumps(pricing, sort_keys=True)
                    expected_pricing_hash = hashlib.sha256(
                        pricing_str.encode()
                    ).hexdigest()[:32]

                    if pricing_hash != expected_pricing_hash:
                        fail("Pricing tampering detected")
                    else:
                        ok("Pricing binding valid")

                    # --------------------------------
                    # RTT HASH CHECK
                    # --------------------------------
                    expected_rtt = TokenFactory._hash(payload_rtt)

                    if expected_rtt != tx.get("rtt"):
                        fail("RTT hash mismatch")
                    else:
                        ok("RTT hash valid")

        # --------------------------------
        # 4. ROUTE BINDING
        # --------------------------------
        route = tx.get("route_result")

        if route:
            expected_hash = compute_route_hash(route, tx.get("rtt"))

            if tx.get("route_hash") != expected_hash:
                fail("Route tampering detected")
            else:
                ok("Route binding valid")
        else:
            result["checks"].append({
                "status": "INFO",
                "msg": "No route attached"
            })

        # --------------------------------
        # 5. UTT STATUS
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
        return {
            "valid": False,
            "error": str(e)
        }