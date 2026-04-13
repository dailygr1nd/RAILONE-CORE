import time

from audit import append_log
from fx_corridor import validate_corridor, quote_conversion
from user_accounts import debit_account, credit_account

# BANK RAILS
from bank_ke import process_transfer as bank_ke_transfer
from bank_tz import process_transfer as bank_tz_transfer
from bank_ug import process_transfer as bank_ug_transfer

# PSP RAILS
from psp_ke import process_transfer as psp_ke_transfer
from psp_tz import process_transfer as psp_tz_transfer
from psp_ug import process_transfer as psp_ug_transfer

# SMOVE IMT RAIL
from smove_wallet import process_transfer as smove_transfer


class TransactionEngine:

    # --------------------------
    # RAIL RESOLUTION
    # --------------------------
    def resolve_rail(self, account_id):
        if not account_id:
            return "UNKNOWN"

        if "BANK_KE" in account_id:
            return "BANK_KE"
        if "BANK_TZ" in account_id:
            return "BANK_TZ"
        if "BANK_UG" in account_id:
            return "BANK_UG"

        if "PSP_KE" in account_id:
            return "PSP_KE"
        if "PSP_TZ" in account_id:
            return "PSP_TZ"
        if "PSP_UG" in account_id:
            return "PSP_UG"

        if "SMV" in account_id or "SMOVE" in account_id:
            return "SMOVE"

        return "UNKNOWN"

    # --------------------------
    # MAIN ENTRY POINT
    # --------------------------
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

        # --------------------------
        # CORRIDOR VALIDATION
        # --------------------------
        if not validate_corridor(sender_currency, receiver_currency):
            return False, "Unsupported corridor", utt

        quote = quote_conversion(amount, sender_currency, receiver_currency)

        converted_amount = quote["converted_amount"]
        fx_rate = quote["fx_rate"]

        # --------------------------
        # DEBIT (LOCK FUNDS FIRST)
        # --------------------------
        ok, debit_result = debit_account(sender_id, debit_account_id, amount)

        if not ok:
            return False, debit_result, utt

        sender_rail = self.resolve_rail(debit_account_id)
        receiver_rail = self.resolve_rail(credit_account_id)

        # --------------------------
        # ROUTE LOGGING (IMPORTANT)
        # --------------------------
        append_log("ROUTE_SELECTED", {
            "utt": utt,
            "rtt": rtt,
            "sender_rail": sender_rail,
            "receiver_rail": receiver_rail,
            "amount": amount,
            "converted_amount": converted_amount,
            "fx_rate": fx_rate
        })

        # --------------------------
        # EXECUTE ROUTE
        # --------------------------
        result = self.dispatch(
            sender_rail,
            receiver_rail,
            sender_id,
            receiver_id,
            amount,
            converted_amount,
            debit_account_id,
            credit_account_id,
            sender_currency,
            receiver_currency,
            utt,
            rtt
        )

        # --------------------------
        # FAILURE HANDLING
        # --------------------------
        if not result["success"]:
            credit_account(sender_id, debit_account_id, amount)

            append_log("FINAL_STATE", {
                "tx_id": rtt,
                "utt": utt,
                "status": "FAILED",
                "reason": result.get("reason", "ROUTE_FAILED")
            })

            return False, result.get("reason", "ROUTE_FAILED"), utt

        # --------------------------
        # CREDIT RECEIVER
        # --------------------------
        credit_ok, message = credit_account(
            receiver_id,
            credit_account_id,
            converted_amount
        )

        if not credit_ok:
            credit_account(sender_id, debit_account_id, amount)

            append_log("FINAL_STATE", {
                "tx_id": rtt,
                "utt": utt,
                "status": "FAILED",
                "reason": "CREDIT_FAILED"
            })

            return False, message, utt

        # --------------------------
        # FINAL LEDGER ENTRY
        # --------------------------
        append_log("FINAL_STATE", {
            "tx_id": rtt,
            "utt": utt,
            "sender": sender_id,
            "receiver": receiver_id,
            "amount": amount,
            "converted_amount": converted_amount,
            "fx_rate": fx_rate,
            "sender_rail": sender_rail,
            "receiver_rail": receiver_rail,
            "status": "SUCCESS"
        })

        return True, "Transaction successful", utt

    # --------------------------
    # DISPATCH ENGINE
    # --------------------------
    def dispatch(
        self,
        sender_rail,
        receiver_rail,
        sender_id,
        receiver_id,
        amount,
        converted_amount,
        debit_account_id,
        credit_account_id,
        sender_currency,
        receiver_currency,
        utt,
        rtt
    ):

        route = f"{sender_rail}_TO_{receiver_rail}"

        # --------------------------
        # BANK → BANK
        # --------------------------
        if "BANK" in sender_rail and "BANK" in receiver_rail:
            return {"success": True}

        # --------------------------
        # PSP → PSP
        # --------------------------
        if "PSP" in sender_rail and "PSP" in receiver_rail:
            return {"success": True}

        # --------------------------
        # BANK ↔ PSP (LOCAL INTEROP)
        # --------------------------
        if ("BANK" in sender_rail and "PSP" in receiver_rail) or \
           ("PSP" in sender_rail and "BANK" in receiver_rail):
            return {"success": True}

        # --------------------------
        # SMOVE AS GLOBAL FX / IMT LAYER
        # --------------------------
        if sender_rail == "SMOVE" or receiver_rail == "SMOVE":

            return smove_transfer(
                sender_id,
                receiver_id,
                amount,
                sender_currency,
                receiver_currency,
                rtt,
                utt
            )

        return {"success": False, "reason": "NO_ROUTE_MATCH"}