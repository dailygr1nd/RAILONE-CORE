# ==============================
# tx_verifier.py (FULL PROTOCOL VERIFIER)
# ==============================

from token_factory import TokenFactory


def verify_transaction(tx: dict, institution_id="R1CORE") -> dict:

    result = {
        "valid": True,
        "checks": []
    }

    def fail(reason):
        result["valid"] = False
        result["checks"].append({"status": "FAIL", "reason": reason})

    def ok(msg):
        result["checks"].append({"status": "OK", "msg": msg})

    try:
        # --------------------------------
        # 1. ETK-S CHECK
        # --------------------------------
        etk_s = tx.get("etk_s")
        if not etk_s:
            fail("ETK-S missing")
        else:
            ok("ETK-S present")

        # --------------------------------
        # 2. ETK-R DERIVATION CHECK
        # --------------------------------
        etk_r = tx.get("etk_r")
        if not etk_r:
            fail("ETK-R missing")
        else:
            # recompute expected ETK-R payload
            expected_payload = f"ETK-R|{etk_s}|{tx['receiver_account']}"
            expected_hash = TokenFactory._hash(expected_payload)

            if expected_hash != etk_r:
                fail("ETK-R derivation mismatch")
            else:
                ok("ETK-R valid")

        # --------------------------------
        # 3. RTT CHECK
        # --------------------------------
        rtt = tx.get("rtt")

        expected_rtt_payload = f"RTT|{etk_s}|{etk_r}|{tx['tx_id']}"
        expected_rtt = TokenFactory._hash(expected_rtt_payload)

        if expected_rtt != rtt:
            fail("RTT mismatch")
        else:
            ok("RTT valid")

        # --------------------------------
        # 4. ROUTE BINDING CHECK
        # --------------------------------
        route = tx.get("route_result")

        if route:
            expected_route_hash = f"{route}-{rtt}"
            if tx.get("route_hash") != expected_route_hash:
                fail("Route tampering detected")
            else:
                ok("Route binding valid")

        # --------------------------------
        # 5. UTT CHECK
        # --------------------------------
        utt = tx.get("utt")

        if not utt:
            fail("UTT missing (not finalized)")
        else:
            ok("UTT present")

        return result

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }