# routing.py

from routing_brain import compute_rail_health

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

    if account_id.startswith("SMOVE"):
        return "SMOVE"

    return "UNKNOWN"


def get_best_rail(candidate_rails, cross_border=False):
    """
    Returns best rail based on intelligence scoring.
    """

    best = None
    best_score = -999

    for rail in candidate_rails:
        score = compute_rail_health(rail)

        if cross_border and rail == "SMOVE":
            score += 2

        if score > best_score:
            best_score = score
            best = rail

    return best