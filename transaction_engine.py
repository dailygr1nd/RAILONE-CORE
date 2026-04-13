# transaction_engine.py
import time

from audit import append_log
from fx_corridor import validate_corridor, quote_conversion
from user_accounts import (
    debit_account,
    credit_account,
    get_account_balance,
)

from smove_wallet import process_transfer as smove_transfer


class TransactionEngine:
    def __init__(self):
        pass

    # ---------------------------------
    # RAIL RESOLUTION
    # ---------------------------------
    def resolve_rail(self, account_id):
        account_id = account_id.upper()

        if account_id.startswith("BANK_KE"):
            return "BANK_KE"

        if account_id.startswith("BANK_TZ"):
            return "BANK_TZ"

        if account_id.startswith("BANK_UG"):
            return "BANK_UG"

        if (
            account_id.startswith("PSP_MPESA_KE")
            or account_id.startswith("PSP_AIRTEL_KE")
        ):
            return "PSP_KE"

        if (
            account_id.startswith("PSP_MPESA_TZ")
            or account_id.startswith("PSP_AIRTEL_TZ")
        ):
            return "PSP_TZ"

        if account_id.startswith("PSP_AIRTEL_UG"):
            return "PSP_UG"

        if account_id.startswith("SMV"):
            return "SMOVE"

        return "UNKNOWN"

    # ---------------------------------
    # DISPATCH LAYER
    # ---------------------------------
    def dispatch(
        self,
        sender_rail,
        receiver_rail,
        sender_id,
        receiver_id,
        amount,
        sender_currency,
        receiver_currency,
        rtt,
        utt,
    ):
        # same-family transfers
        if sender_rail.startswith("BANK") and (
            receiver_rail.startswith("BANK")
            or receiver_rail.startswith("PSP")
        ):
            return {"success": True}

        if sender_rail.startswith("PSP") and (
            receiver_rail.startswith("BANK")
            or receiver_rail.startswith("PSP")
        ):
            return {"success": True}

        # any SmOve corridor
        if sender_rail == "SMOVE" or receiver_rail == "SMOVE":
            return smove_transfer(
                sender_id=sender_id,
                receiver_id=receiver_id,
                amount=amount,
                sender_currency=sender_currency,
                receiver_currency=receiver_currency,
                rtt=rtt,
                utt=utt,
            )

        return {
            "success": False,
            "reason": "NO_ROUTE_MATCH",
        }

    # ---------------------------------
    # MAIN ENGINE
    # ---------------------------------
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

        # corridor validation
        if not validate_corridor(
            sender_currency,
            receiver_currency,
        ):
            return False, "Unsupported corridor", utt

        quote = quote_conversion(
            amount,
            sender_currency,
            receiver_currency,
        )

        converted_amount = quote["converted_amount"]
        fx_rate = quote["fx_rate"]

        # lock sender funds
        ok, msg = debit_account(
            sender_id,
            debit_account_id,
            amount,
        )

        if not ok:
            return False, msg, utt

        sender_rail = self.resolve_rail(debit_account_id)
        receiver_rail = self.resolve_rail(credit_account_id)

        append_log(
            "ROUTE_SELECTED",
            {
                "rtt": rtt,
                "utt": utt,
                "sender_rail": sender_rail,
                "receiver_rail": receiver_rail,
                "amount": amount,
                "converted_amount": converted_amount,
                "fx_rate": fx_rate,
                "chain_version": "v2_bank_defensible",
            },
        )

        result = self.dispatch(
            sender_rail,
            receiver_rail,
            sender_id,
            receiver_id,
            amount,
            sender_currency,
            receiver_currency,
            rtt,
            utt,
        )

        if not result["success"]:
            credit_account(
                sender_id,
                debit_account_id,
                amount,
            )

            append_log(
                "FINAL_STATE",
                {
                    "tx_id": rtt,
                    "utt": utt,
                    "status": "FAILED",
                    "reason": result["reason"],
                    "chain_version": "v2_bank_defensible",
                },
            )

            return False, result["reason"], utt

        credit_ok, credit_msg = credit_account(
            receiver_id,
            credit_account_id,
            converted_amount,
        )

        if not credit_ok:
            credit_account(
                sender_id,
                debit_account_id,
                amount,
            )

            return False, credit_msg, utt

        append_log(
            "FINAL_STATE",
            {
                "tx_id": rtt,
                "utt": utt,
                "sender": sender_id,
                "receiver": receiver_id,
                "amount": amount,
                "converted_amount": converted_amount,
                "fx_rate": fx_rate,
                "sender_rail": sender_rail,
                "receiver_rail": receiver_rail,
                "status": "SUCCESS",
                "chain_version": "v2_bank_defensible",
            },
        )

        return True, "Transaction successful", utt


def initiate_transaction(*args, **kwargs):
    engine = TransactionEngine()
    return engine.create_transaction(*args, **kwargs)