# routing.py
from telemetry import get_telemetry

RAILS = [
    "BANK_KE",
    "BANK_TZ",
    "BANK_UG",
    "PSP_KE",
    "PSP_TZ",
    "PSP_UG",
    "SMOVE"
]


def classify_rail(account_id):
    if account_id.startswith("BANK_KE"):
        return "BANK_KE"

    if account_id.startswith("BANK_TZ"):
        return "BANK_TZ"

    if account_id.startswith("BANK_UG"):
        return "BANK_UG"

    if account_id.startswith("PSP_MPESA_KE") or account_id.startswith("PSP_AIRTEL_KE"):
        return "PSP_KE"

    if account_id.startswith("PSP_MPESA_TZ") or account_id.startswith("PSP_AIRTEL_TZ"):
        return "PSP_TZ"

    if account_id.startswith("PSP_AIRTEL_UG"):
        return "PSP_UG"

    if account_id.startswith("SMV"):
        return "SMOVE"

    return "UNKNOWN"


def get_candidate_rails(sender_acc, receiver_acc):
    sender = classify_rail(sender_acc)
    receiver = classify_rail(receiver_acc)

    return {
        "sender": sender,
        "receiver": receiver,
        "cross_border": sender != receiver
    }
