import time
from audit import append_log
from fx_corridor import validate_corridor, quote_conversion
from user_accounts import debit_account, credit_account, get_account_balance
from psp_cross import process as psp_process


class TransactionEngine:
    def create_transaction(
        self,
        sender_id,
        receiver_id,
        amount,
        debit_account_id,
        credit_account_id,
        sender_currency,
        receiver_currency,
        tx_id=None,
        utt=None,
    ):
        utt = utt or f"UTT-{int(time.time() * 1000)}"
        rtt = tx_id or f"RTT-{int(time.time() * 1000)}"

        if not validate_corridor(sender_currency, receiver_currency):
            return False, "Unsupported corridor", utt

        quote = quote_conversion(
            amount,
            sender_currency,
            receiver_currency,
        )

        converted_amount = quote["converted_amount"]
        fx_rate = quote["fx_rate"]

        ok, debit_result = debit_account(
            sender_id,
            debit_account_id,
            amount,
        )

        if not ok:
            return False, debit_result, utt

        route = {
            "sender": {
                "nid": sender_id,
                "currency": sender_currency,
                "balance": get_account_balance(sender_id, debit_account_id),
            },
            "receiver": {
                "nid": receiver_id,
                "currency": receiver_currency,
            },
            "rail": debit_account_id.split("-")[0],
            "ref_id": utt,
            "ttl": time.time() + 60,
        }

        result = psp_process(amount, route, etk_hash=utt)

        if not result["success"]:
            debit_account(receiver_id, credit_account_id, 0)
            credit_account(sender_id, debit_account_id, amount)
            return False, result.get("Reason"), utt

        credit_ok, message = credit_account(
            receiver_id,
            credit_account_id,
            converted_amount,
        )

        if not credit_ok:
            credit_account(sender_id, debit_account_id, amount)
            return False, message, utt

        append_log("BANK_RESPONSE", {
            "success": True,
            "Status": "Executed",
            "RTT": rtt,
            "UTT": utt,
            "fx_rate": fx_rate,
            "converted_amount": converted_amount,
        })

        return True, "Transaction successful", utt
