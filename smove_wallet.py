import time
import random
from datetime import datetime

from corridor_fx_model import quote_conversion, validate_corridor
from user_accounts import debit_account, credit_account
from ledger import log_transaction


# --------------------------
# SMOVE CONFIG
# --------------------------
SUPPORTED = ["USD", "EUR", "GBP", "NGN", "ZAR", "EGP"]


# --------------------------
# VALIDATION
# --------------------------
def validate_currency(ccy):
    return ccy in SUPPORTED


# --------------------------
# CORE IMT TRANSFER ENGINE
# --------------------------
def process_transfer(
    sender_id,
    receiver_id,
    amount,
    sender_acc,
    receiver_acc,
    sender_ccy,
    receiver_ccy,
    rtt,
    utt,
):
    """
    SmOve IMT Rail:
    - multi-currency wallet transfer system
    - FX conversion layer
    - ledger logging
    - account state mutation
    """

    timestamp = datetime.utcnow().isoformat()

    # --------------------------
    # VALIDATION LAYER
    # --------------------------
    if not validate_currency(sender_ccy) or not validate_currency(receiver_ccy):
        return {
            "success": False,
            "reason": "UNSUPPORTED_SMOVE_CURRENCY",
            "rtt": rtt,
            "utt": utt,
        }

    # --------------------------
    # FX LAYER
    # --------------------------
    quote = quote_conversion(amount, sender_ccy, receiver_ccy)
    converted_amount = quote["converted_amount"]
    fx_rate = quote["fx_rate"]

    # --------------------------
    # DEBIT SENDER
    # --------------------------
    ok, debit_msg = debit_account(sender_id, sender_acc, amount)

    if not ok:
        return {
            "success": False,
            "reason": debit_msg,
            "rtt": rtt,
            "utt": utt,
        }

    # --------------------------
    # SIMULATED SETTLEMENT RISK
    # --------------------------
    settlement_success = random.random() > 0.03  # 97% success rate

    tx_id = f"SMV-{int(time.time() * 1000)}"

    # --------------------------
    # LEDGER ENTRY (ALWAYS CREATED)
    # --------------------------
    sender = {"identity_token": sender_id}
    receiver = {"identity_token": receiver_id}

    entry = log_transaction(
        tx_id=tx_id,
        rtt=rtt,
        utt=utt,
        sender=sender,
        receiver=receiver,
        amount=amount,
        currency=sender_ccy,
        rail="SMOVE",
    )

    # --------------------------
    # FAILURE PATH
    # --------------------------
    if not settlement_success:
        entry["status"] = "FAILED"

        # rollback sender debit
        credit_account(sender_id, sender_acc, amount)

        return {
            "success": False,
            "reason": "SMOVE_SETTLEMENT_FAILURE",
            "tx_id": tx_id,
            "rtt": rtt,
            "utt": utt,
        }

    # --------------------------
    # CREDIT RECEIVER
    # --------------------------
    ok, credit_msg = credit_account(receiver_id, receiver_acc, converted_amount)

    if not ok:
        # rollback full sender restore
        credit_account(sender_id, sender_acc, amount)

        entry["status"] = "FAILED"

        return {
            "success": False,
            "reason": credit_msg,
            "tx_id": tx_id,
            "rtt": rtt,
            "utt": utt,
        }

    # --------------------------
    # SUCCESS FINALIZATION
    # --------------------------
    entry["status"] = "SETTLED"

    return {
        "success": True,
        "tx_id": tx_id,
        "converted_amount": converted_amount,
        "fx_rate": fx_rate,
        "timestamp": timestamp,
        "rtt": rtt,
        "utt": utt,
        "rail": "SMOVE",
    }