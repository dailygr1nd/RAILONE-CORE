# ==============================
# failure_handler.py (FIXED)
# ==============================

from liquidity_engine import release_liquidity


def handle_failure(tx, router, settlement, error):

    print(f"[FAILURE] {error}")

    try:
        sender_inst = tx.payload["sender"]["institution"]
        sender_acc = tx.payload["sender"]["account"]
        amount = tx.payload["amount"]["value"]

        # --------------------------------
        # ROLLBACK: RELEASE RESERVED FUNDS
        # --------------------------------
        if tx.has_attestation("FUNDS_RESERVED"):

            print("[ROLLBACK] Releasing sender funds...")

            router.call(
                sender_inst,
                "release_funds",
                sender_acc,
                amount
            )

        else:
            print("[ROLLBACK] No funds reserved.")

        # --------------------------------
        # ROLLBACK: RELEASE LIQUIDITY
        # --------------------------------
        if hasattr(tx, "route"):

            for hop in tx.route:

                currency_pair = tx.payload["amount"]["currency"] + "_" + tx.payload["amount"]["currency"]

                try:
                    release_liquidity(currency_pair, amount)
                except Exception:
                    pass  # safe ignore

    except Exception as rollback_error:
        print(f"[CRITICAL] Rollback failed: {rollback_error}")

    tx.set_state("FAILED")

    return tx.get_summary()
