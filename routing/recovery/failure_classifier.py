# ==========================================
# recovery/failure_classifier.py
# RailOne Enterprise Failure Taxonomy
# ==========================================

FAILURE_MAP = {

    # -------------------------
    # TIMEOUTS
    # -------------------------
    "PROVIDER_TIMEOUT":
        "TIMEOUT",

    "BANK_TIMEOUT":
        "TIMEOUT",

    "NETWORK_TIMEOUT":
        "TIMEOUT",

    "SOCKET_TIMEOUT":
        "TIMEOUT",

    "REQUEST_TIMEOUT":
        "TIMEOUT",

    # -------------------------
    # RAIL DOWN
    # -------------------------
    "MPESA_UNAVAILABLE":
        "RAIL_DOWN",

    "BANK_OFFLINE":
        "RAIL_DOWN",

    "PSP_UNAVAILABLE":
        "RAIL_DOWN",

    "INSTITUTION_DOWN":
        "RAIL_DOWN",

    # -------------------------
    # LIQUIDITY
    # -------------------------
    "INSUFFICIENT_FLOAT":
        "LOW_LIQUIDITY",

    "FLOAT_EXHAUSTED":
        "LOW_LIQUIDITY",

    "NO_SETTLEMENT_LIQUIDITY":
        "LOW_LIQUIDITY",

    "POOL_DEPLETED":
        "LOW_LIQUIDITY",

    # -------------------------
    # DESTINATION
    # -------------------------
    "INVALID_ACCOUNT":
        "DESTINATION_INVALID",

    "ACCOUNT_NOT_FOUND":
        "DESTINATION_INVALID",

    "BENEFICIARY_UNKNOWN":
        "DESTINATION_INVALID",

    # -------------------------
    # COMPLIANCE
    # -------------------------
    "KYC_FAILED":
        "COMPLIANCE_BLOCK",

    "AML_BLOCK":
        "COMPLIANCE_BLOCK",

    "SANCTIONS_HIT":
        "COMPLIANCE_BLOCK",

    # -------------------------
    # DUPLICATE
    # -------------------------
    "DUPLICATE_TRANSACTION":
        "DUPLICATE",

    "IDEMPOTENCY_CONFLICT":
        "DUPLICATE",

    # -------------------------
    # INTEGRITY
    # -------------------------
    "INVALID_SIGNATURE":
        "INTEGRITY_FAILURE",

    "RTT_VERIFICATION_FAILED":
        "INTEGRITY_FAILURE",

    "TOKEN_EXPIRED":
        "INTEGRITY_FAILURE",
}


def classify_failure(error):

    error = str(error).upper()

    for key, value in FAILURE_MAP.items():

        if key in error:

            return value

    return "UNKNOWN"