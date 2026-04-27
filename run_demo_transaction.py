from transaction_envelope import TransactionEnvelope
from settlement_engine import SettlementEngine
from failure_handler import handle_failure


def run_demo_transaction(router, user_links):

    settlement = SettlementEngine()

    sender = user_links["PSP_KE"]
    receiver = user_links["BANK_TZ"]

    tx = TransactionEnvelope({
        "sender": sender,
        "receiver": receiver,
        "amount": {"value": 10000, "currency": "KES"}
    })

    try:
        # 1. VERIFY
        settlement.advance(tx, "VERIFIED")

        # 2. FUNDS CHECK
        res = router.call(
            sender["institution"],
            "verify_funds",
            sender["account"],
            10000
        )

        if res["status"] != "OK":
            raise Exception("INSUFFICIENT_FUNDS")

        tx.add_attestation(sender["institution"], "FUNDS_AVAILABLE", res["attestation"])

        # 3. RESERVE
        res = router.call(
            sender["institution"],
            "reserve_funds",
            sender["account"],
            10000
        )

        tx.add_attestation(sender["institution"], "FUNDS_RESERVED", res["attestation"])

        settlement.advance(tx, "FUNDS_RESERVED")

        # 4. EXECUTION
        settlement.advance(tx, "EXECUTING")

        res = router.call(
            receiver["institution"],
            "receive_funds",
            receiver["account"],
            185000
        )

        tx.add_attestation(receiver["institution"], "SETTLED", res["attestation"])

        settlement.advance(tx, "SETTLED")

        # 5. FINAL
        settlement.advance(tx, "FINAL")

        return tx.get_summary()

    except Exception as e:
        return handle_failure(tx, router, settlement, str(e))