# ==============================
# execution/execution_verifier.py
# RailOne Deterministic
# Execution Verification Engine
# ==============================

import json
import hashlib

from crypto.token_factory import (
    TokenFactory
)


# ==========================================
# ROUTE REALIZATION HASH
# RTT-bound deterministic route proof
# ==========================================
def compute_route_hash(

    route,

    rtt_id
):

    route_str = json.dumps({

        "type":
            route.get("type"),

        "rail":
            route.get("rail"),

        "cost":
            round(
                route.get(
                    "cost",
                    0
                ),
                6
            )

    }, sort_keys=True)

    return hashlib.sha256(

        f"{route_str}|{rtt_id}".encode()

    ).hexdigest()


# ==========================================
# VERIFY EXECUTION CONTINUITY
# ==========================================
def verify_execution(

    execution: dict,

    institution_id="R1CORE"
):

    result = {

        "valid": True,

        "checks": []
    }

    # ==========================================
    # FAILURE HANDLER
    # ==========================================
    def fail(reason):

        result["valid"] = False

        result["checks"].append({

            "status":
                "FAIL",

            "reason":
                reason
        })

    # ==========================================
    # SUCCESS HANDLER
    # ==========================================
    def ok(message):

        result["checks"].append({

            "status":
                "OK",

            "message":
                message
        })

    try:

        # ==========================================
        # EXECUTION CONTINUITY
        # ==========================================
        if not execution.get(
            "utt_id"
        ):

            fail(
                "UTT_ID_MISSING"
            )

        else:

            ok(
                "UTT continuity present"
            )

        # ==========================================
        # ROUTE REALIZATION
        # ==========================================
        if not execution.get(
            "rtt_id"
        ):

            fail(
                "RTT_ID_MISSING"
            )

        else:

            ok(
                "RTT realization present"
            )

        # ==========================================
        # IDENTITY CONTINUITY
        # ==========================================
        if not execution.get(
            "continuity_uid"
        ):

            fail(
                "CONTINUITY_UID_MISSING"
            )

        else:

            ok(
                "Identity continuity present"
            )

        # ==========================================
        # EXECUTION TRUST KEYS
        # ==========================================
        if not execution.get(
            "etk_s"
        ):

            fail(
                "ETK_S_MISSING"
            )

        else:

            ok(
                "ETK-S present"
            )

        if not execution.get(
            "etk_r"
        ):

            fail(
                "ETK_R_MISSING"
            )

        else:

            ok(
                "ETK-R present"
            )

        # ==========================================
        # RTT VERIFICATION
        # ==========================================
        payload = execution.get(
            "payload_rtt"
        )

        sig_hex = execution.get(
            "rtt_signature"
        )

        if not payload or not sig_hex:

            fail(
                "RTT_PAYLOAD_OR_SIGNATURE_MISSING"
            )

        else:

            signature = bytes.fromhex(
                sig_hex
            )

            if not TokenFactory.verify(

                payload,

                signature,

                institution_id
            ):

                fail(
                    "RTT_SIGNATURE_INVALID"
                )

            else:

                ok(
                    "RTT signature valid"
                )

            # ==========================================
            # RTT HASH VALIDATION
            # ==========================================
            expected_rtt = (
                TokenFactory._hash(
                    payload
                )
            )

            if expected_rtt != (
                execution.get(
                    "rtt_id"
                )
            ):

                fail(
                    "RTT_HASH_MISMATCH"
                )

            else:

                ok(
                    "RTT hash valid"
                )

        # ==========================================
        # ROUTE BINDING
        # ==========================================
        if execution.get(
            "route_result"
        ):

            expected_hash = (

                compute_route_hash(

                    execution[
                        "route_result"
                    ],

                    execution[
                        "rtt_id"
                    ]
                )
            )

            if expected_hash != (
                execution.get(
                    "route_hash"
                )
            ):

                fail(
                    "ROUTE_TAMPERING_DETECTED"
                )

            else:

                ok(
                    "Route binding valid"
                )

        # ==========================================
        # EXECUTION VALUE
        # ==========================================
        amount = execution.get(
            "amount"
        )

        if amount is None:

            fail(
                "EXECUTION_AMOUNT_MISSING"
            )

        elif amount <= 0:

            fail(
                "INVALID_EXECUTION_AMOUNT"
            )

        else:

            ok(
                "Execution amount valid"
            )

        # ==========================================
        # EXECUTION ACTORS
        # ==========================================
        if not execution.get(
            "sender_account"
        ):

            fail(
                "SENDER_ACCOUNT_MISSING"
            )

        else:

            ok(
                "Sender account valid"
            )

        if not execution.get(
            "receiver_account"
        ):

            fail(
                "RECEIVER_ACCOUNT_MISSING"
            )

        else:

            ok(
                "Receiver account valid"
            )

        # ==========================================
        # EXECUTION STATE
        # ==========================================
        if not execution.get(
            "state"
        ):

            fail(
                "EXECUTION_STATE_MISSING"
            )

        else:

            ok(
                "Execution state present"
            )

        # ==========================================
        # REPLAY LINEAGE
        # ==========================================
        if execution.get(
            "replay_generation"
        ) is not None:

            ok(
                f"Replay generation: "
                f"{execution.get('replay_generation')}"
            )

        if execution.get(
            "lineage_parent"
        ):

            ok(
                "Lineage ancestry present"
            )

        # ==========================================
        # VERIFICATION COMPLETE
        # ==========================================
        if result["valid"]:

            ok(
                "Execution continuity verified"
            )

        return result

    except Exception as e:

        return {

            "valid": False,

            "error":
                str(e)
        }