# transaction_engine.py

from audit import append_log
from fx_corridor import validate_corridor, quote_conversion
from handshake import run_handshake
from user_accounts import (
    debit_account,
    credit_account,
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
        # Bank ↔ Bank / PSP
        if sender_rail.startswith("BANK") and (
            receiver_rail.startswith("BANK")
            or receiver_rail.startswith("PSP")
        ):
            return {"success": True}

        # PSP ↔ Bank / PSP
        if sender_rail.startswith("PSP") and (
            receiver_rail.startswith("BANK")
            or receiver_rail.startswith("PSP")
        ):
            return {"success": True}

        # SmOve corridor
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
    ):
        # -----------------------------
        # HANDSHAKE + TOKEN GENERATION
        # -----------------------------
        handshake = run_handshake(
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            currency=sender_currency,
        )

        utt = handshake["utt"]
        rtt = handshake["rtt"]

        # -----------------------------
        # CORRIDOR VALIDATION
        # -----------------------------
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

        # -----------------------------
        # LOCK SENDER FUNDS
        # -----------------------------
        ok, msg = debit_account(
            sender_id,
            debit_account_id,
            amount,
        )

        if not ok:
            append_log(
                "FINAL_STATE",
                {
                    "rtt": rtt,
                    "utt": utt,
                    "status": "FAILED",
                    "reason": msg,
                },
            )
            return False, msg, utt

        # -----------------------------
        # ROUTE RESOLUTION
        # -----------------------------
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
                "chain_version": "v3_fintech_state_machine",
            },
        )

        # -----------------------------
        # DISPATCH
        # -----------------------------
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

        # -----------------------------
        # FAILURE ROLLBACK
        # -----------------------------
        if not result["success"]:
            credit_account(
                sender_id,
                debit_account_id,
                amount,
            )

            append_log(
                "FINAL_STATE",
                {
                    "rtt": rtt,
                    "utt": utt,
                    "status": "FAILED",
                    "reason": result["reason"],
                },
            )

            return False, result["reason"], utt

        # -----------------------------
        # RECEIVER CREDIT
        # -----------------------------
        credit_ok, credit_msg = credit_account(
            receiver_id,
            credit_account_id,
            converted_amount,
        )

        if not credit_ok:
            # rollback sender
            credit_account(
                sender_id,
                debit_account_id,
                amount,
            )

            append_log(
                "FINAL_STATE",
                {
                    "rtt": rtt,
                    "utt": utt,
                    "status": "ROLLED_BACK",
                    "reason": credit_msg,
                },
            )

            return False, credit_msg, utt

        # -----------------------------
        # SUCCESS FINALIZATION
        # -----------------------------
        append_log(
            "FINAL_STATE",
            {
                "rtt": rtt,
                "utt": utt,
                "sender": sender_id,
                "receiver": receiver_id,
                "amount": amount,
                "converted_amount": converted_amount,
                "fx_rate": fx_rate,
                "sender_rail": sender_rail,
                "receiver_rail": receiver_rail,
                "status": "SUCCESS",
                "chain_version": "v3_fintech_state_machine",
            },
        )

        return True, "Transaction successful", utt


def initiate_transaction(*args, **kwargs):
    engine = TransactionEngine()
    return engine.create_transaction(*args, **kwargs)